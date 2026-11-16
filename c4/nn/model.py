"""The value network: "how good is this board for the player to move?"   OWNER: Sriyanth

The network never chooses moves. The search (c4/search.py) asks it to score
positions at the depth limit, exactly like the hand-written evaluator.

Input  (N, 3, 6, 7) float tensor, made by c4.selfplay.dataset.encode():
         plane 0 = stones of the player to move, plane 1 = opponent's stones,
         plane 2 = cells that can be played next.  Row 0 = bottom.
Output (N,) values in (-1, 1): +1 = player to move wins, -1 = loses, 0 = draw.

Architecture (proposal 4.2)
  4 x [Conv 3x3, 64 filters, BatchNorm, ReLU]      padding 1, so the board stays 6x7
  1 x [Conv 1x1, 8 filters,  BatchNorm, ReLU]      squeezes 64 channels to 8
  Linear(8*6*7 -> 128), ReLU, Linear(128 -> 1), tanh

About 157k parameters. Without the 1x1 squeeze the Linear layer alone would be
64*42*128 = 344k parameters (about 457k in total), so the 1x1 layer is what keeps
the network at the size given in the proposal and fast enough on a CPU.
"""
from __future__ import annotations

from pathlib import Path

import torch
from torch import nn

from c4.board import HEIGHT, WIDTH

IN_PLANES = 3


class C4Net(nn.Module):
    def __init__(self, channels: int = 64, n_conv: int = 4, head_channels: int = 8,
                 hidden: int = 128):
        super().__init__()
        self.config = dict(channels=channels, n_conv=n_conv,
                           head_channels=head_channels, hidden=hidden)
        layers: list[nn.Module] = []
        c_in = IN_PLANES
        for _ in range(n_conv):
            layers += [nn.Conv2d(c_in, channels, kernel_size=3, padding=1),
                       nn.BatchNorm2d(channels), nn.ReLU(inplace=True)]
            c_in = channels
        layers += [nn.Conv2d(channels, head_channels, kernel_size=1),
                   nn.BatchNorm2d(head_channels), nn.ReLU(inplace=True)]
        self.body = nn.Sequential(*layers)
        self.head = nn.Sequential(
            nn.Flatten(),
            nn.Linear(head_channels * HEIGHT * WIDTH, hidden), nn.ReLU(inplace=True),
            nn.Linear(hidden, 1), nn.Tanh(),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.head(self.body(x)).squeeze(-1)


def count_parameters(model: nn.Module) -> int:
    return sum(p.numel() for p in model.parameters())


def save_checkpoint(model: C4Net, path, info: dict | None = None) -> None:
    """Weights + architecture + training notes in one file (models/ is git-ignored)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    torch.save({"config": model.config, "state_dict": model.state_dict(),
                "info": info or {}}, path)


def load_checkpoint(path, device: str = "cpu") -> tuple[C4Net, dict]:
    ckpt = torch.load(path, map_location=device, weights_only=True)
    model = C4Net(**ckpt["config"])
    model.load_state_dict(ckpt["state_dict"])
    model.to(device).eval()
    return model, ckpt.get("info", {})
