# Conventions

## 目录约定

- `scripts/`：可执行脚本
- `configs/`：通用配置和模板
- `ansible/`：主机清单与 playbook
- `k8s/`：Kubernetes 清单
- `helm/values/`：Helm values 文件

## 命名建议

- 脚本名使用小写下划线，例如 `sync_logs.py`
- YAML 文件尽量体现环境和用途，例如 `prod-values.yaml`
- 文档优先写清楚输入、输出、依赖和执行方式
