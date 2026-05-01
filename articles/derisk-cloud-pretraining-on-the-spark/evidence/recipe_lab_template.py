"""Recipe-lab template — point the A4 agent loop at a 7B-shaped target.

The A4 agent loop in `articles/autoresearch-agent-loop/evidence/agent_loop.py`
sweeps a 200M-param proxy model on the Spark — small enough to finish 60-step
taste tests in ~80 seconds, large enough that the kernel and memory shapes
are honest. To use the same harness for derisking a 7B-class cloud pretrain,
swap two things: the architectural target (the dimensions you're searching
over) and the proxy scaling rule (how Spark-measured numbers translate to
the cloud target).

This is a sketch, not a runnable script. Copy the relevant pieces into the
A4 harness when you're ready to run a real recipe-lab session.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class TargetArchitecture:
    """The cloud-bound architecture you want to pretrain.

    Hold these constants fixed during the Spark sweep. The sweep varies the
    proxy_dim / proxy_layers / proxy_seq inside known ratios, then projects
    the chosen shape up to (target_dim, target_layers, target_seq) for the
    final cloud run. Maintain head_dim, ffn_ratio, and mlp_activation across
    the projection — those carry the strongest scaling signal.
    """

    target_params: int = 7_000_000_000
    target_dim: int = 4096
    target_layers: int = 32
    target_heads: int = 32
    target_seq: int = 8192
    target_vocab: int = 128_256
    head_dim: int = 128
    ffn_ratio: float = 3.5
    mlp_activation: str = "swiglu"


@dataclass(frozen=True)
class ProxyMenu:
    """The knob menu the A4 agent searches over on the Spark.

    These are the *proxy* dimensions — small enough to fit a 60-step taste
    test on one Spark in ~80 seconds. The menu's ratios match the target
    architecture so the search transfers: same head_dim, same ffn_ratio,
    same activation, scaled-down dim/layers/seq.
    """

    d_model_choices: tuple = (512, 768, 1024)
    n_head_choices: tuple = (4, 6, 8)
    n_layer_choices: tuple = (8, 12, 16)
    seq_len_choices: tuple = (512, 1024, 2048)
    learning_rate_choices: tuple = (1e-4, 3e-4, 1e-3)
    batch_size_choices: tuple = (8, 16, 32)
    precision_choices: tuple = ("bf16", "fp8")


def project_to_target(proxy_cfg: dict, target: TargetArchitecture) -> dict:
    """Project a Spark-measured proxy config to its cloud-target equivalent.

    The Spark sweep tells you the *shape* that wins (relative deltas in
    val_bpb across knob settings); this function maps that shape onto the
    target architecture's actual dimensions for the cloud run. Keep the
    shape ratios; ignore the proxy's absolute scale.
    """
    return {
        "d_model": target.target_dim,
        "n_head": target.target_heads,
        "n_layer": target.target_layers,
        "seq_len": target.target_seq,
        "vocab_size": target.target_vocab,
        "head_dim": target.head_dim,
        "ffn_ratio": target.ffn_ratio,
        "mlp_activation": target.mlp_activation,
        "learning_rate": proxy_cfg["learning_rate"]
        * (proxy_cfg["d_model"] / target.target_dim) ** 0.5,
        "batch_size": proxy_cfg["batch_size"],
        "precision": proxy_cfg["precision"],
    }


# To wire this into A4's harness:
#
#   1. Import ProxyMenu and project_to_target into agent_loop.py.
#   2. Replace the hard-coded knob menu in the Proposer with ProxyMenu's
#      tuples (or a derived MenuSpec).
#   3. After the loop completes, read trajectory.jsonl, pick the top-3
#      candidates by val_bpb, and call project_to_target on each.
#   4. Hand those three projected configs to your cloud orchestrator —
#      they are the architectures worth booking H100 hours for.
