# Multi-machine / home GPU topology

Run web/API/PostgreSQL on an application host and local inference on one or more private
Linux/NVIDIA hosts. Configure private URLs/firewall/auth keys; do not publish database or
inference ports. Training should have a separate environment and resource allocation.
GPU diagnostics and actual model tests are prerequisites; this topology was not executed.

Separate machines/GPUs do not provide pooled VRAM. Replication serves independent requests
on separate model copies. Tensor parallelism shards one model only with supported serving
configuration, GPU compatibility and adequate intra/inter-host interconnects; ordinary home
Ethernet can be unsuitable. Do not claim cluster memory/throughput without measurement.
Kubernetes/schedulers/automatic routing are future scale requirements, not this Compose MVP.
