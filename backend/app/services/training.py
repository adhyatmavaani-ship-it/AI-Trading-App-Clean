from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

from app.services.model_registry import ModelRegistry

try:  # pragma: no cover - environment dependent
    import torch
    from torch import nn
    from torch.optim import AdamW
except ModuleNotFoundError:  # pragma: no cover - environment dependent
    torch = None
    nn = None
    AdamW = None


@dataclass
class TrainingService:
    registry: ModelRegistry

    def train(self, features: np.ndarray, future_returns: np.ndarray, labels: np.ndarray) -> dict:
        scaler = StandardScaler()
        x_scaled = scaler.fit_transform(features)
        self.registry.save_scaler(scaler)

        classifier = self.registry.load_classifier()
        classifier.fit(x_scaled, labels)
        self.registry.save_classifier(classifier)

        val_loss = 0.0
        if torch is not None and self.registry.sequence_model_supported():
            from app.models.lstm_transformer import LSTMTransformer

            x_train, x_val, y_train, y_val = train_test_split(
                x_scaled, future_returns, test_size=0.2, random_state=42
            )
            x_train_tensor = torch.tensor(x_train[:, None, :], dtype=torch.float32)
            y_train_tensor = torch.tensor(y_train, dtype=torch.float32)
            x_val_tensor = torch.tensor(x_val[:, None, :], dtype=torch.float32)
            y_val_tensor = torch.tensor(y_val, dtype=torch.float32)

            model = LSTMTransformer(input_size=x_scaled.shape[1])
            optimizer = AdamW(model.parameters(), lr=1e-3, weight_decay=1e-4)
            criterion = nn.HuberLoss()

            for _ in range(25):
                optimizer.zero_grad()
                loss = criterion(model(x_train_tensor), y_train_tensor)
                loss.backward()
                optimizer.step()

            with torch.no_grad():
                val_loss = criterion(model(x_val_tensor), y_val_tensor).item()
            self.registry.save_sequence_model(model)
        version = self.registry.bump_version()
        return {"validation_loss": val_loss, "samples": int(features.shape[0]), "model_version": version}
