"""
EnzAIme — Model architecture, baselines, group-split and metrics
=================================================================
Small, honest supervised pipeline. The MLP is intentionally tiny because we
only have ~70 unique enzymes; the embeddings are FROZEN (never fine-tuned).

Input vector per (enzyme, scenario) row:

  [ ESM embedding (D)
    pollutant one-hot
    scenario_ph, temperature, salinity (standardised)
    evidence/pollutant score
    metadata availability flags (has_ph, has_temp, has_sal, has_seq, has_acc)
    metadata_completeness
    unknown_feature_count ]

Target: the TRANSPARENT `derived_compatibility_label` (see label_generation.py).
All evaluation metrics are agreement with that derived label — NEVER
experimental degradation efficiency.

Leakage prevention (CRITICAL, Step 9):
    Every row is generated from an enzyme. A random row split would put
    scenarios of the same enzyme in both train and test (near-duplicate
    rows -> inflated, meaningless scores). We therefore ALWAYS group by
    enzyme_id:
      - GroupShuffleSplit (default) or GroupKFold for CV
    and document it in reports/evaluation_protocol.md.

Run: (imported by src/train_kaggle.py and tests)
"""
from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

SRC_DIR = Path(__file__).resolve().parent
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

__all__ = [
    "SUPPORTED_POLLUTANTS", "build_env_feature_columns",
    "build_feature_matrix", "GroupSplitter", "fit_ridge", "fit_random_forest",
    "evaluate_regression", "SuitabilityMLP", "train_mlp", "set_seed",
]

SUPPORTED_POLLUTANTS = ["PET", "PUR", "PA", "PE", "PP"]
SEED = 42


def set_seed(seed: int = SEED) -> None:
    import random
    random.seed(seed)
    np.random.seed(seed)
    try:
        import torch
        torch.manual_seed(seed)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(seed)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Feature construction
# ---------------------------------------------------------------------------
def build_env_feature_columns(pollutants: list[str]) -> list[str]:
    cols = []
    for p in pollutants:
        cols.append(f"pollutant_{p}")
    cols += [
        "scenario_ph_norm", "scenario_temp_norm", "scenario_sal_norm",
        "pollutant_evidence_score", "ph_metadata_available",
        "temperature_metadata_available", "salinity_metadata_available",
        "has_sequence", "has_accession", "metadata_completeness",
        "unknown_feature_count",
    ]
    return cols


def build_feature_matrix(df: pd.DataFrame,
                         pollutant_cats: list[str] | None = None,
                         scale: bool = True,
                         scaler=None):
    """Build environment-feature matrix (without the ESM embedding block).
    Returns (X_env: np.ndarray float32, scaler, columns)."""
    cats = pollutant_cats or sorted(df["pollutant_type"].dropna().unique().tolist())
    rows = []
    for _, r in df.iterrows():
        onehot = [1.0 if str(r["pollutant_type"]) == p else 0.0 for p in cats]
        rows.append(onehot + [
            float(r.get("scenario_ph", np.nan)),
            float(r.get("scenario_temperature_c", np.nan)),
            float(r.get("scenario_salinity", np.nan)),
            float(r.get("pollutant_evidence_score", r.get("evidence_score", 0.0) or 0.0)),
            int(r.get("ph_metadata_available", r.get("has_ph_opt", 0) or 0)),
            int(r.get("temperature_metadata_available", r.get("has_temperature_opt", 0) or 0)),
            int(r.get("salinity_metadata_available", r.get("has_salinity_data", 0) or 0)),
            int(r.get("has_sequence", 0) or 0),
            int(r.get("has_accession", 0) or 0),
            float(r.get("metadata_completeness", r.get("has_sequence", 0) or 0)),
            int(r.get("unknown_feature_count", 0) or 0),
        ])
    X = np.array(rows, dtype=np.float32)
    if scale:
        from sklearn.preprocessing import StandardScaler
        if scaler is None:
            scaler = StandardScaler()
            X_env = scaler.fit_transform(X)
        else:
            X_env = scaler.transform(X)
    else:
        X_env, scaler = X, scaler
    return np.asarray(X_env, dtype=np.float32), scaler, cats


def merge_embeddings(table: pd.DataFrame, embeddings: dict, expected_dim: int) -> np.ndarray:
    """Stack frozen embeddings in table order; raises if any enzyme missing."""
    ids = table["enzyme_id"].tolist()
    rows = [embeddings[eid] for eid in ids]
    arr = np.stack(rows).astype(np.float32)
    if arr.shape[1] != expected_dim:
        raise ValueError(f"embedding dim mismatch: expected {expected_dim}, got {arr.shape[1]}")
    return arr


# ---------------------------------------------------------------------------
# Leakage prevention (Step 9)
# ---------------------------------------------------------------------------
@dataclass
class GroupSplitter:
    """Split index arrays by enzyme groups (no enzyme straddles train/test)."""
    n_splits: int = 5
    test_size: float = 0.2
    seed: int = SEED

    def train_test_indices(self, enzymes: pd.Series):
        from sklearn.model_selection import GroupShuffleSplit
        groups = enzymes.to_numpy()
        idx = np.arange(len(enzymes))
        gss = GroupShuffleSplit(n_splits=1, test_size=self.test_size, random_state=self.seed)
        train_idx, test_idx = next(gss.split(idx, groups=groups))
        return train_idx, test_idx

    def cv_indices(self, enzymes: pd.Series):
        from sklearn.model_selection import GroupKFold
        unique_groups = sorted(enzymes.unique())
        if len(unique_groups) < self.n_splits:
            yield from self._holdout(enzymes)
            return
        gkf = GroupKFold(n_splits=self.n_splits)
        groups = enzymes.to_numpy()
        idx = np.arange(len(enzymes))
        for train_idx, test_idx in gkf.split(idx, groups=groups):
            yield train_idx, test_idx

    def _holdout(self, enzymes: pd.Series):
        """Single documented enzyme-level holdout when too few groups for K-fold."""
        unique_groups = sorted(enzymes.unique())
        n_test = max(1, round(len(unique_groups) * 0.3))
        rng = np.random.RandomState(self.seed)
        rng.shuffle(unique_groups)
        test_ids = set(unique_groups[:n_test])
        idx = np.arange(len(enzymes))
        groups = np.asarray(enzymes)
        train_idx = idx[[g not in test_ids for g in groups]]
        test_idx = idx[[g in test_ids for g in groups]]
        yield train_idx, test_idx

    def no_leakage(self, groups_train: np.ndarray, groups_test: np.ndarray) -> bool:
        return not bool(set(groups_train.astype(str)) & set(groups_test.astype(str)))


# ---------------------------------------------------------------------------
# Baseline estimators (sklearn, no deep learning)
# ---------------------------------------------------------------------------
def fit_ridge(X, y, seed: int = SEED):
    from sklearn.linear_model import Ridge
    return Ridge(alpha=1.0, random_state=seed).fit(X, y)


def fit_random_forest(X, y, seed: int = SEED):
    from sklearn.ensemble import RandomForestRegressor
    return RandomForestRegressor(n_estimators=300, max_depth=6, min_samples_leaf=2,
                                 random_state=seed, n_jobs=-1).fit(X, y)


def fit_gradient_boosting(X, y, seed: int = SEED):
    from sklearn.ensemble import GradientBoostingRegressor
    return GradientBoostingRegressor(n_estimators=200, max_depth=3,
                                     learning_rate=0.05, random_state=seed).fit(X, y)


# ---------------------------------------------------------------------------
# Metrics (agreement with the derived label, clearly documented)
# ---------------------------------------------------------------------------
def evaluate_regression(y_true: np.ndarray, y_pred: np.ndarray) -> dict:
    from scipy.stats import spearmanr
    from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    rho = spearmanr(y_true, y_pred).correlation
    return {
        "mae": round(float(mean_absolute_error(y_true, y_pred)), 4),
        "rmse": round(float(np.sqrt(mean_squared_error(y_true, y_pred))), 4),
        "r2": round(float(r2_score(y_true, y_pred)), 4) if y_pred.var() > 0 else None,
        "spearman": round(float(rho), 4) if rho is not None else None,
        "n": int(len(y_true)),
    }


def top_k_consistency(y_true: np.ndarray, y_pred: np.ndarray, k: int = 3) -> dict:
    """Fraction of rows whose enzyme would stay in the top-k by true label."""
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    if len(y_true) < k:
        return {"top1_consistent": None, f"top{k}_consistent": None, "n": len(y_true)}
    order_pred = np.argsort(-y_pred)
    order_true = np.argsort(-y_true)
    topk_pred = set(order_pred[:k])
    top1_cons = int(order_pred[0] in order_true[:1])
    topk_cons = len(topk_pred & set(order_true[:k])) / k
    return {"top1_consistent": top1_cons, f"top{k}_consistent": round(topk_cons, 4),
            "n": len(y_true)}


# ---------------------------------------------------------------------------
# Small neural model (Step 8)
# ---------------------------------------------------------------------------
class SuitabilityMLP:
    """Wraps a small nn.Module with fit/predict and checkpoint save/load.
    Kept tiny: 2 dense blocks + dropout + residual around the second block."""

    def __init__(self, embedding_dim: int, env_dim: int, hidden: int = 64,
                 dropout: float = 0.3, seed: int = SEED):
        import torch
        import torch.nn as nn
        self._torch = torch
        self._nn = nn
        self.seed = seed
        self.has_torch = True

        class _Net(nn.Module):
            def __init__(self, ed, vd, hd, dp):
                super().__init__()
                self.proj = nn.Sequential(
                    nn.Linear(ed + vd, hd), nn.BatchNorm1d(hd), nn.ReLU(), nn.Dropout(dp))
                self.hidden = nn.Sequential(
                    nn.Linear(hd, hd), nn.BatchNorm1d(hd), nn.ReLU(), nn.Dropout(dp))
                self.out = nn.Linear(hd, 1)

            def forward(self, emb, env):
                x = torch.cat([emb, env], dim=-1)
                h1 = self.proj(x)
                h2 = self.hidden(h1)
                return torch.sigmoid(self.out(h2 + h1)).squeeze(-1)

        self.net = _Net(embedding_dim, env_dim, hidden, dropout)
        self.net.eval()

    def _t(self, X, device):
        return self._torch.tensor(np.asarray(X, dtype=np.float32), device=device)

    def fit(self, X_emb, X_env, y, n_epochs: int = 300, batch_size: int = 256,
            lr: float = 1e-3, weight_decay: float = 1e-4,
            patience: int = 20, X_val_emb=None, X_val_env=None, y_val=None,
            device: str = "cpu") -> dict:
        import torch
        import torch.nn as nn
        torch.manual_seed(self.seed)
        X_emb = np.asarray(X_emb, dtype=np.float32)
        X_env = np.asarray(X_env, dtype=np.float32)
        y = np.asarray(y, dtype=np.float32)

        data = torch.utils.data.TensorDataset(
            self._t(X_emb, device), self._t(X_env, device), self._t(y, device))
        loader = torch.utils.data.DataLoader(data, batch_size=batch_size, shuffle=True)

        val_loader = None
        if X_val_emb is not None:
            val_loader = torch.utils.data.DataLoader(
                torch.utils.data.TensorDataset(
                    self._t(X_val_emb, device), self._t(X_val_env, device), self._t(y_val, device)),
                batch_size=1024)

        self.net.to(device).train()
        opt = torch.optim.Adam(self.net.parameters(), lr=lr, weight_decay=weight_decay)
        loss_fn = nn.MSELoss()

        best_val = float("inf")
        best_state = None
        bad_epochs = 0
        history = {"train_loss": [], "val_loss": []}
        for epoch in range(1, n_epochs + 1):
            self.net.train()
            epoch_loss = 0.0
            for eb, vb, yb in loader:
                opt.zero_grad()
                pred = self.net(eb, vb)
                loss = loss_fn(pred, yb)
                loss.backward()
                opt.step()
                epoch_loss += loss.item() * eb.shape[0]
            history["train_loss"].append(round(epoch_loss / max(1, len(data)), 5))

            if val_loader is not None:
                self.net.eval()
                with torch.no_grad():
                    vpreds, vtrue = [], []
                    for eb, vb, yb in val_loader:
                        vpreds.append(self.net(eb, vb).cpu())
                        vtrue.append(yb.cpu())
                    vloss = loss_fn(torch.cat(vpreds), torch.cat(vtrue)).item()
                history["val_loss"].append(round(float(vloss), 5))
                if vloss < best_val - 1e-5:
                    best_val, bad_epochs = float(vloss), 0
                    best_state = {k: v.clone() for k, v in self.net.state_dict().items()}
                else:
                    bad_epochs += 1
                    if bad_epochs >= patience:
                        print(f"[mlp] early stop @ epoch {epoch} (val_best={best_val:.5f})")
                        break
            else:
                best_state = {k: v.clone() for k, v in self.net.state_dict().items()}

        if best_state is not None:
            self.net.load_state_dict(best_state)
        self.net.eval()
        return {"best_val_mse": float(best_val) if best_val < float("inf") else None,
                "last_epoch": epoch, "history": history}

    def predict(self, X_emb, X_env, device="cpu") -> np.ndarray:
        self.net.to(device).eval()
        with self._torch.no_grad():
            out = []
            for i in range(0, len(X_emb), 512):
                eb = self._t(X_emb[i:i + 512], device)
                vb = self._t(X_env[i:i + 512], device)
                out.append(self.net(eb, vb).cpu().numpy())
            return np.concatenate(out)

    def save(self, path: Path, feature_config: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self._torch.save(self.net.state_dict(), str(path))
        import json
        (path.parent / "feature_config.json").write_text(
            json.dumps(feature_config, indent=2, default=str))

    @classmethod
    def load(cls, path: Path, feature_config: dict, embedding_dim: int,
             env_dim: int, device="cpu"):
        import torch
        m = cls(embedding_dim, env_dim, hidden=feature_config.get("hidden_dim", 64),
                dropout=feature_config.get("dropout", 0.3))
        state = torch.load(str(path), map_location=device)
        if "state_dict" in state:
            state = state["state_dict"]
        m.net.load_state_dict(state)
        m.net.to(device).eval()
        return m


# Backend-compatible converter (Step 10): train the SAME old-style
# SuitabilityNet so DEMO_MODE=false keeps working unchanged.
def train_backend_compatible_model(X_emb, env_v6, y, device="cpu",
                                   n_epochs=300, lr=1e-3, patience=20):
    """X_emb: NxD embeddings; env_v6: N x [pollonehot(3) , ph_norm, t_norm, s_norm].
    Returns SuitabilityNet already fitted + saved artifact dict."""
    import torch

    sys.path.insert(0, str(SRC_DIR.parent / "common"))
    from enzaime_core.model import SuitabilityNet

    model = SuitabilityNet(embedding_dim=X_emb.shape[1], env_feature_dim=env_v6.shape[1])
    model.to(device).train()
    opt = torch.optim.Adam(model.parameters(), lr=lr, weight_decay=1e-4)
    loss_fn = torch.nn.MSELoss()
    Xe = torch.tensor(X_emb, dtype=torch.float32, device=device)
    Xv = torch.tensor(env_v6, dtype=torch.float32, device=device)
    yt = torch.tensor(y, dtype=torch.float32, device=device)

    best_state, best_loss, bad = None, float("inf"), 0
    n = len(y)
    idx = np.arange(n)
    for epoch in range(1, n_epochs + 1):
        np.random.shuffle(idx)
        model.train()
        for i in range(0, n, 256):
            b = idx[i:i + 256]
            opt.zero_grad()
            loss = loss_fn(model(Xe[b], Xv[b]), yt[b])
            loss.backward()
            opt.step()
        model.eval()
        with torch.no_grad():
            v = float(loss_fn(model(Xe, Xv), yt).item())
        if v < best_loss - 1e-6:
            best_loss, bad = v, 0
            best_state = {k: c.clone() for k, c in model.state_dict().items()}
        else:
            bad += 1
            if bad >= patience:
                break
    if best_state is not None:
        model.load_state_dict(best_state)
    return model, best_state, best_loss