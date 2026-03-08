# infra-automation

集中维护运维脚本、自动化配置、Kubernetes YAML、Helm values 和项目文档。

## 项目目标

- 统一存放常用运维脚本
- 沉淀自动化工具配置和模板
- 管理不同环境的部署清单
- 保留操作文档和规范说明

## 目录结构

```text
infra-automation/
├── ansible/
│   ├── inventory/
│   └── playbooks/
├── configs/
├── docs/
├── helm/
│   └── values/
├── k8s/
│   ├── base/
│   └── overlays/
│       ├── dev/
│       └── prod/
└── scripts/
```

## 目录说明

- `scripts/`：可直接执行的运维脚本
- `configs/`：通用配置、YAML 模板、工具配置文件
- `ansible/`：主机清单和 Playbook
- `k8s/`：Kubernetes 资源清单，按 `base/overlays` 区分环境
- `helm/values/`：不同环境或不同服务的 Helm values
- `docs/`：使用说明、规范和操作文档

## 当前脚本

`scripts/latest_package.py`

作用：扫描指定目录并返回最新版本的安装包路径，避免手动输入具体版本号。

使用示例：

```bash
python3 scripts/latest_package.py /data/packages
python3 scripts/latest_package.py /data/packages --name myapp
```

## 维护约定

- 脚本优先使用 Python 或 Shell，要求可直接在服务器执行
- 配置文件尽量按环境拆分，例如 `dev`、`test`、`prod`
- 新增脚本时，补充用途、输入参数和执行示例
- 文档优先写清楚依赖、执行方式和风险说明
