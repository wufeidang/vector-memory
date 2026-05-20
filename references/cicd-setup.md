# Vector-Memory CI/CD 配置

## 前提
- GitHub 账号：wufeidang，邮箱：740812008@qq.com
- 本地仓库已在 `~/.hermes/skills/vector_memory/` 完成 `git init` + 首次 commit
- workflow 文件：`.github/workflows/test.yml`（缓存模型 + 运行 pytest）

## 推送到 GitHub

```bash
cd ~/.hermes/skills/vector_memory
git remote add origin https://github.com/wufeidang/vector-memory.git
git push -u origin master
```

首次推送需登录 GitHub（Windows 凭据管理器记住密码）。

## CI 流程

```
push → GitHub Actions → 安装 Python 3.10 + 依赖
     → 缓存 modelscope 模型（~/.cache/modelscope，首次下载 ~3min）
     → pytest 30 个测试全部通过 = ✅
```

## 日常提交

```bash
cd ~/.hermes/skills/vector_memory
git add -A
git commit -m "fix: 改了xxx"
git push
```

## 常见问题

- **push 被拒**：`git pull --rebase origin master && git push`
- **要求密码**：配 SSH 密钥 → `ssh-keygen -t ed25519 -C "740812008@qq.com"`，公钥贴到 GitHub Settings → SSH keys
- **SSH 推送**：`git remote set-url origin git@github.com:wufeidang/vector-memory.git`