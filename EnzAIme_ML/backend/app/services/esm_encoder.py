import torch
from transformers import AutoTokenizer, AutoModel


MODEL_NAME = "facebook/esm2_t33_650M_UR50D"


class ESMEncoder:
    def __init__(self):
        self.device = torch.device(
            "cuda" if torch.cuda.is_available() else "cpu"
        )

        self.tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)

        self.model = AutoModel.from_pretrained(
            MODEL_NAME,
            torch_dtype=torch.float16 if self.device.type == "cuda" else torch.float32,
        )

        self.model = self.model.to(self.device)
        self.model.eval()

        for parameter in self.model.parameters():
            parameter.requires_grad = False

    def encode(self, sequence: str):
        sequence = sequence.strip().upper()

        if not sequence:
            raise ValueError("Protein sequence cannot be empty.")

        inputs = self.tokenizer(
            sequence,
            return_tensors="pt",
            truncation=True,
            max_length=1024,
        )

        inputs = {
            key: value.to(self.device)
            for key, value in inputs.items()
        }

        with torch.no_grad():
            outputs = self.model(**inputs)

        hidden_states = outputs.last_hidden_state

        attention_mask = inputs["attention_mask"]

        mask = attention_mask.unsqueeze(-1).expand(hidden_states.size()).float()

        summed = torch.sum(hidden_states * mask, dim=1)
        counts = torch.clamp(mask.sum(dim=1), min=1e-9)

        embedding = summed / counts

        return embedding.squeeze(0).float().cpu().numpy()