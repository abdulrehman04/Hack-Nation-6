"""Group tokens into reading-order lines: top-to-bottom, then left-to-right."""

from __future__ import annotations

from dataclasses import dataclass, field

from .readers import Token


@dataclass
class Line:
    """One horizontal row of tokens, left-to-right."""

    y: float
    tokens: list[Token] = field(default_factory=list)

    @property
    def text(self) -> str:
        return " ".join(t.text for t in self.tokens)

    @property
    def x0(self) -> float:
        return min(t.bbox[0] for t in self.tokens)


def _center_y(token: Token) -> float:
    return (token.bbox[1] + token.bbox[3]) / 2


def group_lines(tokens: list[Token], y_tolerance: float = 4.0) -> list[Line]:
    """Bucket tokens whose vertical centers fall within a tolerance into a line."""
    lines: list[Line] = []
    for token in sorted(tokens, key=lambda t: (-_center_y(t), t.bbox[0])):
        yc = _center_y(token)
        for line in lines:
            if abs(line.y - yc) <= y_tolerance:
                line.tokens.append(token)
                break
        else:
            lines.append(Line(y=yc, tokens=[token]))
    for line in lines:
        line.tokens.sort(key=lambda t: t.bbox[0])
    return lines
