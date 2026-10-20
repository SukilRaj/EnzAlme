"""Optional trained Tm model; absence never produces a fabricated stability score."""
import json
from pathlib import Path
import numpy as np
import torch
from backend.app.services.neural_oracle import AttentionOracle, batch_features


class StabilityOracle:
    def __init__(self, directory):
        directory = Path(directory)
        self.meta = json.loads((directory / 'manifest.json').read_text())
        if self.meta.get('target') != 'tm_c' or self.meta.get('schema_version') != 1:
            raise ValueError('Unsupported stability checkpoint')
        self.model = AttentionOracle(**self.meta['architecture'])
        self.model.load_state_dict(torch.load(directory / 'weights.pt', map_location='cpu', weights_only=True))
        self.model.eval()
        self.mean = np.array(self.meta['environment_mean'], dtype=np.float32)
        self.std = np.array(self.meta['environment_std'], dtype=np.float32)
        if not np.isfinite(self.std).all() or np.any(self.std <= 0):
            raise ValueError('Invalid stability normalization')

    def predict(self, item, ph):
        sequence, mask, image = batch_features([item])
        environment = np.array([[ph, 1., 0.]], dtype=np.float32)
        with torch.inference_mode():
            score, _ = self.model(sequence, mask, image, torch.zeros(1), torch.tensor((environment-self.mean)/self.std))
        tm = float(score[0])*self.meta['target_std']+self.meta['target_mean']
        if not np.isfinite(tm):
            raise ValueError('Nonfinite stability prediction')
        return tm
