"""Kaggle Tm model: frozen residue embeddings, Attention1D, pH/missingness inputs.

Targets are standardized on training data only. Splits join exact-sequence and
database-protein identities to keep linked records together; not a homology split.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import numpy as np
import torch
from sklearn.model_selection import GroupShuffleSplit
from backend.app.services.neural_oracle import AttentionOracle, batch_features

ENCODER = "facebook/esm2_t12_35M_UR50D"


def linked_groups(rows):
    parents = list(range(len(rows)))
    def find(i):
        while parents[i] != i:
            parents[i] = parents[parents[i]]
            i = parents[i]
        return i
    seen = {}
    for i, row in enumerate(rows):
        for key in ("sequence:"+row["sequence_sha256"], "protein:"+row["family_group"]):
            if key in seen:
                parents[find(i)] = find(seen[key])
            seen[key] = i
    return np.array([find(i) for i in range(len(rows))])


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--records", default="data/stability/records.json")
    p.add_argument("--features", default="data/stability/features")
    p.add_argument("--output", default="models/stability")
    p.add_argument("--epochs", type=int, default=150)
    p.add_argument("--seed", type=int, default=42)
    args = p.parse_args()
    if args.epochs < 1:
        p.error("epochs must be positive")
    raw = Path(args.records).read_bytes()
    rows = json.loads(raw)
    if not rows:
        raise ValueError("No stability records. Run scripts.collect_stability_data first.")
    for r in rows:
        if r["target_kind"] != "Tm" or r["target_unit"] != "degC" or not r["sequence_mapping_verified"]:
            raise ValueError("Only sequence-verified measured Tm records in Celsius are supported")
        if hashlib.sha256(r["sequence"].encode()).hexdigest() != r["sequence_sha256"]:
            raise ValueError("Sequence digest mismatch")
    directory = Path(args.features)
    directory.mkdir(parents=True, exist_ok=True)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    unique = {r["sequence_sha256"]: r["sequence"] for r in rows}
    missing = [sha for sha in unique if not (directory / f"{sha}.npz").is_file()]
    if missing:
        from transformers import AutoModel, AutoTokenizer
        tokenizer = AutoTokenizer.from_pretrained(ENCODER)
        encoder = AutoModel.from_pretrained(ENCODER).to(device).eval()
        for n, sha in enumerate(missing):
            sequence = unique[sha]
            if not 1 <= len(sequence) <= 1022 or set(sequence)-set("ACDEFGHIKLMNPQRSTVWY"):
                raise ValueError("Unsupported sequence")
            with torch.inference_mode():
                tokens = tokenizer(sequence, return_tensors="pt").to(device)
                features = encoder(**tokens).last_hidden_state[0, 1:len(sequence)+1].cpu().numpy()
            np.savez_compressed(directory / f"{sha}.npz", sequence=features, encoder=np.array(ENCODER))
            if n % 25 == 0:
                print(f"Embedded {n+1}/{len(missing)} sequences", flush=True)
        del encoder
        if device == "cuda":
            torch.cuda.empty_cache()
    feature_map = {}
    for sha in unique:
        with np.load(directory / f"{sha}.npz", allow_pickle=False) as f:
            if str(f["encoder"].item()) != ENCODER:
                raise ValueError("Cached encoder does not match")
            feature_map[sha] = {"sequence": f["sequence"].astype(np.float32), "image": np.zeros(512, dtype=np.float32)}
    groups = linked_groups(rows)
    if len(set(groups)) < 10:
        raise ValueError("At least ten independent protein/sequence groups required")
    rest, test = next(GroupShuffleSplit(n_splits=1, test_size=.2, random_state=args.seed).split(rows, groups=groups))
    a, b = next(GroupShuffleSplit(n_splits=1, test_size=.25, random_state=args.seed+1).split(rest, groups=groups[rest]))
    train, validation = rest[a], rest[b]
    y = np.array([r["tm_c"] for r in rows], dtype=np.float32)
    ph = np.array([r.get("ph") if isinstance(r.get("ph"), (int,float)) and 0 <= r["ph"] <= 14 else np.nan for r in rows], dtype=np.float32)
    observed_ph = np.isfinite(ph)
    ph_median = float(np.median(ph[train][observed_ph[train]])) if observed_ph[train].any() else 7.
    environment = np.stack([np.where(observed_ph, ph, ph_median), observed_ph.astype(np.float32), np.zeros(len(rows))], 1).astype(np.float32)
    mean, std = environment[train].mean(0), environment[train].std(0).clip(1e-6)
    ymean, ystd = float(y[train].mean()), max(float(y[train].std()), 1e-6)
    if not np.isfinite(y).all() or any(not np.isfinite(f["sequence"]).all() for f in feature_map.values()):
        raise ValueError("Nonfinite training data")
    rng = np.random.default_rng(args.seed)
    torch.manual_seed(args.seed)
    model = AttentionOracle().to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=5e-4, weight_decay=1e-2)
    target = (y-ymean)/ystd
    def predict(ids):
        features = [feature_map[rows[i]["sequence_sha256"]] for i in ids]
        seq, mask, image = batch_features(features, device)
        return model(seq, mask, image, torch.zeros(len(ids), device=device),
                     torch.tensor((environment[ids]-mean)/std, device=device))[0]
    def predictions(ids):
        with torch.inference_mode():
            return np.concatenate([predict(batch).cpu().numpy() for batch in np.array_split(ids, max(1,int(np.ceil(len(ids)/16))))])
    best, weights, wait = float("inf"), None, 0
    for epoch in range(args.epochs):
        model.train()
        for batch in np.array_split(rng.permutation(train), max(1,int(np.ceil(len(train)/16)))):
            optimizer.zero_grad()
            loss = torch.nn.functional.mse_loss(predict(batch), torch.tensor(target[batch], device=device))
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 5)
            optimizer.step()
        model.eval()
        mse = float(np.mean((predictions(validation)-target[validation])**2))
        if mse < best:
            best, weights, wait = mse, copy.deepcopy(model.state_dict()), 0
        else:
            wait += 1
        print(f"Epoch {epoch+1}: validation RMSE {np.sqrt(mse)*ystd:.3f} C", flush=True)
        if wait >= 15:
            break
    if weights is None:
        raise ValueError("Training did not produce finite validation loss")
    model.load_state_dict(weights)
    pred = predictions(test)*ystd+ymean
    observed = y[test]
    metrics = {"mae_c": float(np.abs(pred-observed).mean()), "rmse_c": float(np.sqrt(np.mean((pred-observed)**2))),
        "r2": float(1-np.sum((pred-observed)**2)/np.sum((observed-observed.mean())**2)) if np.var(observed)>0 else None,
        "training_median_mae_c": float(np.abs(observed-np.median(y[train])).mean()), "test_rows": len(test), "test_groups": len(set(groups[test]))}
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    torch.save({k:v.cpu() for k,v in weights.items()}, out / "weights.pt")
    manifest = {"schema_version": 1, "target": "tm_c", "encoder": ENCODER,
        "architecture": {"sequence_dim":480,"image_dim":512,"hidden":64},
        "environment_mean":mean.tolist(), "environment_std":std.tolist(), "ph_median":ph_median,
        "target_mean":ymean,"target_std":ystd,"dataset_sha256":hashlib.sha256(raw).hexdigest(),
        "status":"research_checkpoint", "image_trained":False, "test_metrics":metrics,
        "seed":args.seed, "records":len(rows),
        "split_record_ids":{name:[rows[i]['record_id'] for i in ids] for name,ids in [('train',train),('validation',validation),('test',test)]},
        "limitations":["Wild-type Tm model; mutation-effect prediction is unvalidated.","Database protein/sequence groups, not homology or study splits.","Assay method and buffer effects are not modeled."]}
    (out / 'manifest.json').write_text(json.dumps(manifest,indent=2))
    (out / 'held_out_predictions.json').write_text(json.dumps([{'record_id':rows[i]['record_id'],'protein_id':rows[i]['protein_id'],'observed_tm_c':float(o),'predicted_tm_c':float(v)} for i,o,v in zip(test,observed,pred)],indent=2))
    print(json.dumps(metrics,indent=2))


if __name__ == '__main__':
    main()
