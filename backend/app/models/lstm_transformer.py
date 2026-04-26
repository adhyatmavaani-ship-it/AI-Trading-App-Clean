from __future__ import annotations

import torch
from torch import Tensor, nn


class LSTMTransformer(nn.Module):
    """Hybrid sequence model for short-horizon price return forecasting."""

    def __init__(self, input_size: int, hidden_size: int = 64, nhead: int = 4):
        super().__init__()
        self.lstm = nn.LSTM(
            input_size=input_size,
            hidden_size=hidden_size,
            batch_first=True,
            num_layers=2,
            dropout=0.2,
        )
        encoder_layer = nn.TransformerEncoderLayer(
            d_model=hidden_size,
            nhead=nhead,
            dim_feedforward=hidden_size * 4,
            batch_first=True,
            dropout=0.2,
        )
        self.transformer = nn.TransformerEncoder(encoder_layer, num_layers=2)
        self.head = nn.Sequential(
            nn.LayerNorm(hidden_size),
            nn.Linear(hidden_size, hidden_size // 2),
            nn.GELU(),
            nn.Linear(hidden_size // 2, 1),
        )

    def forward(self, inputs: Tensor) -> Tensor:
        lstm_out, _ = self.lstm(inputs)
        encoded = self.transformer(lstm_out)
        return self.head(encoded[:, -1, :]).squeeze(-1)
