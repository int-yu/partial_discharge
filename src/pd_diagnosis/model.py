from __future__ import annotations

import torch
from torch import nn


class ClassificationModel(nn.Module):
    """Architecture used by the legacy-v1 four-class model."""

    def __init__(self, input_size: int = 10, num_classes: int = 4) -> None:
        super().__init__()
        self.fc1 = nn.Linear(input_size, 128)
        self.bn1 = nn.BatchNorm1d(128)
        self.dropout1 = nn.Dropout(0.3)
        self.fc2 = nn.Linear(128, 64)
        self.bn2 = nn.BatchNorm1d(64)
        self.dropout2 = nn.Dropout(0.3)
        self.fc3 = nn.Linear(64, 32)
        self.bn3 = nn.BatchNorm1d(32)
        self.fc4 = nn.Linear(32, 16)
        self.bn4 = nn.BatchNorm1d(16)
        self.fc5 = nn.Linear(16, num_classes)

    def forward(self, values: torch.Tensor) -> torch.Tensor:
        values = torch.relu(self.bn1(self.fc1(values)))
        values = self.dropout1(values)
        values = torch.relu(self.bn2(self.fc2(values)))
        values = self.dropout2(values)
        values = torch.relu(self.bn3(self.fc3(values)))
        values = torch.relu(self.bn4(self.fc4(values)))
        return self.fc5(values)
