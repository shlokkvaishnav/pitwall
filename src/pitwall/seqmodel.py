"""Causal transformer over a driver's laps in a race (spec 17). Needs the optional `deep` extra (torch)."""

from __future__ import annotations

import numpy as np
import pandas as pd
import torch
from torch import nn

from .features import FEATURES

MAX_ROWS = 100
KEYS = ["season", "round", "driver"]


class SeqModel(nn.Module):
    def __init__(
        self, n_features: int = len(FEATURES), dim: int = 64, heads: int = 4, depth: int = 3, dropout: float = 0.1
    ):
        super().__init__()
        self.embed = nn.Linear(n_features, dim)
        self.pos = nn.Embedding(MAX_ROWS, dim)
        layer = nn.TransformerEncoderLayer(dim, heads, 2 * dim, dropout=dropout, batch_first=True, norm_first=True)
        self.enc = nn.TransformerEncoder(layer, depth)
        self.head = nn.Linear(dim, 1)

    def forward(self, x: torch.Tensor, pad: torch.Tensor) -> torch.Tensor:
        """x: (B, T, F); pad: (B, T) True where padded. Returns the delta (B, T)."""
        t = x.shape[1]
        h = self.embed(x) + self.pos(torch.arange(t, device=x.device))[None]
        causal = torch.triu(torch.ones(t, t, dtype=torch.bool, device=x.device), 1)
        return self.head(self.enc(h, mask=causal, src_key_padding_mask=pad)).squeeze(-1)


def sequences(df: pd.DataFrame, mean: np.ndarray, std: np.ndarray) -> list[tuple[np.ndarray, np.ndarray, np.ndarray]]:
    """One (features, delta, row index) per (season, round, driver), in lap order, cut to MAX_ROWS rows."""
    df = df.sort_values([*KEYS, "lap"])
    out = []
    for _, g in df.groupby(KEYS, sort=False):
        x = ((g[FEATURES].to_numpy(float) - mean) / std).astype(np.float32)
        x = np.nan_to_num(x)
        out.append((x[:MAX_ROWS], g["delta"].to_numpy(np.float32)[:MAX_ROWS], g.index.to_numpy()[:MAX_ROWS]))
    return out


def _batch(seqs, device):
    t = max(len(s[0]) for s in seqs)
    x = np.zeros((len(seqs), t, len(FEATURES)), np.float32)
    y = np.zeros((len(seqs), t), np.float32)
    pad = np.ones((len(seqs), t), bool)
    for i, (xi, yi, _) in enumerate(seqs):
        x[i, : len(xi)], y[i, : len(yi)], pad[i, : len(xi)] = xi, yi, False
    return torch.from_numpy(x).to(device), torch.from_numpy(y).to(device), torch.from_numpy(pad).to(device)


def fit_predict_seq(train: pd.DataFrame, test: pd.DataFrame, device, epochs: int = 15, seed: int = 0) -> np.ndarray:
    """Train on `train`, return predicted lap times for the rows of `test` (in test's row order)."""
    torch.manual_seed(seed)
    rng = np.random.default_rng(seed)
    x = train[FEATURES].to_numpy(float)
    mean, std = np.nanmean(x, 0), np.nanstd(x, 0) + 1e-6
    tr = sequences(train, mean, std)
    model = SeqModel().to(device)
    opt = torch.optim.AdamW(model.parameters(), lr=1e-3, weight_decay=1e-2)
    for _ in range(epochs):
        model.train()
        order = rng.permutation(len(tr))
        for i in range(0, len(tr), 32):
            xb, yb, pad = _batch([tr[j] for j in order[i : i + 32]], device)
            out = model(xb, pad)
            loss = (out - yb).abs()[~pad].mean()
            opt.zero_grad()
            loss.backward()
            opt.step()
    model.eval()
    te = sequences(test.reset_index(drop=True), mean, std)
    delta = pd.Series(np.nan, index=range(len(test)))
    with torch.no_grad():
        for i in range(0, len(te), 64):
            chunk = te[i : i + 64]
            xb, _, pad = _batch(chunk, device)
            out = model(xb, pad).cpu().numpy()
            for k, (xi, _, idx) in enumerate(chunk):
                delta.iloc[idx] = out[k, : len(xi)]
    # rows past MAX_ROWS (none in practice) fall back to delta 0, i.e. "next lap = last lap"
    return test["last1"].to_numpy() + delta.fillna(0.0).to_numpy()
