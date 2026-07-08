<div align="center">

# 🤖 Discord Hermes Admin Bot

**Natural-language Discord server administration** — powered by Hermes Planner (LLM strategist) + Discord API executor.

[![Docker](https://img.shields.io/badge/deploy-Docker-%232496ED?logo=docker&logoColor=white)](https://docker.com)
[![Python](https://img.shields.io/badge/python-3.11-%233776AB?logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/planner-FastAPI-%2300C7B7?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Discord](https://img.shields.io/badge/bot-discord.py-%235865F2?logo=discord&logoColor=white)](https://discordpy.readthedocs.io)
[![License](https://img.shields.io/badge/license-MIT-%23FF6B6B)](LICENSE)

*"Tell the bot what you want in plain English — it handles the rest."*

</div>

---

## ✨ Features

| Feature | Description |
|---------|-------------|
| 🗣️ **Natural Language Commands** | `!restructure for  exam this Friday` — the bot plans and executes |
| 🧠 **Hermes Planner AI** | Context-aware strategy engine that understands exams, projects, team dynamics |
| 🔄 **Persistent Memory** | Redis-backed context store — remembers decisions, study plans, projects across restarts |
| 🛡️ **Safety First** | Confirmation gates, protected roles/channels, dry-run previews, action limits |
| 🐳 **One-Command Deploy** | `docker-compose up -d` — runs Discord bot + Planner API + Redis |
| 🎯 **Exam-Aware** | Built-in patterns for exam cram restructures, study groups, pomodoro sessions |
| 🏗️ **Project-Aware** | Auto-creates forums, code-review channels, build voice rooms, team roles |
| 👥 **Role Management** | Auto-assign earned roles (Scholar, Builder, Creative) based on activity |
| 📁 **Channel CRUD** | Text, voice, forum, category — create, delete, rename, set permissions |
| 📊 **Decision Audit** | Every action logged in Redis — full history of what changed and why |

---

## 🏗️ Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│                         Discord Client                               │
│            !create study channels for exam                 │
└──────────────────────────┬───────────────────────────────────────────┘
                           │
┌──────────────────────────▼───────────────────────────────────────────┐
│                      Discord Bot (executor)                           │
│              discord-bot/bot/core.py — AdminBot class                 │
│                                                                       │
│  1. Receives command  →  2. Snapshot server state                     │
│  3. Calls Hermes API  →  4. Shows dry-run preview                    │
│  5. Confirmation UI   →  6. Executes actions safely                  │
└──────────────────────────┬───────────────────────────────────────────┘
                           │  POST /plan  {prompt, guild_context, user_context}
                           ▼
┌──────────────────────────▼───────────────────────────────────────────┐
│                     Hermes Planner (strategist)                        │
│                    hermes-planner/main.py — FastAPI                    │
│                                                                       │
│  1. Loads context from Redis (past decisions, study plans)            │
│  2. Enriches prompt with server schema + user profile                 │
│  3. Calls OpenRouter LLM with strategic system prompt                 │
│  4. Validates & returns structured JSON actions                       │
│  5. Logs decision to Redis for future reference                       │
└──────────────────────────┬───────────────────────────────────────────┘
                           │
              ┌────────────▼────────────┐
              │     Redis (Context)      │
              │  • Server schema         │
              │  • Study plans           │
              │  • Projects              │
              │  • Decision history      │
              └─────────────────────────┘
```

---

## 🚀 Quick Start

### Prerequisites

- [Docker](https://docs.docker.com/get-docker/) + [Docker Compose](https://docs.docker.com/compose/install/)
- [Discord Bot Token](https://discord.com/developers/applications) from the Developer Portal
- [OpenRouter API Key](https://openrouter.ai/keys) for LLM access

### 1. Clone

```bash
git clone https://github.com/HAliveKP/Bot.git
cd Bot
```

### 2. Configure

```bash
cp .env.example .env
```

Edit `.env` with your tokens:

```env
# ── Required ──────────────────────────────────────────────────────────
DISCORD_TOKEN=MTIzNDU2Nzg5MDEyMzQ1Njc4OQ.GxYzZQ.abcdefghijklmnopqrstuvwxyz
OPENROUTER_API_KEY=sk-or-v1-abcdef1234567890abcdef1234567890
GUILD_ID=123456789012345678
ADMIN_USER_IDS=123456789012345678,987654321098765432

# ── Optional (personalises planning) ─────────────────────────────────
HERMES_MODULE=
HERMES_EXAM_DATE=2026-07-10T19:00:00
HERMES_STUDY_HOURS=14
HERMES_TIMEZONE=UTC
```

### 3. Deploy

```bash
docker-compose up -d --build
```

### 4. Invite the Bot

1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. Select your application → **OAuth2 → URL Generator**
3. Scopes: `bot` `applications.commands`
4. Bot Permissions: `Administrator` *(reduce to minimum after setup)*
5. Open the generated URL in your browser → select your server

**Recommended minimum permissions (after setup):**
- Manage Channels
- Manage Roles
- Manage Webhooks
- View Audit Log
- Send Messages
- Embed Links
- Read Message History
- Use Slash Commands

### 5. Verify

```bash
# Check all services are running
docker-compose ps

# Check planner health
curl http://localhost:8000/health

# Follow bot logs
docker-compose logs -f discord-bot
```

### 6. Use It

In any allowed Discord channel or DM:

```
!restructure this server for my  exam on Friday
```

---

## 💬 Example Commands

### 🎯 Exam Cram

```
!restructure server for exam this Friday
!create ST4003 study channels with pomodoro voice rooms
!set up a 3-day cram schedule with day-1 day-2 day-3 channels
```

### 🏗️ Project Lab

```
!start a project lab for my React + FastAPI project
!create Project Alpha with team @John @Sarah
!set up a code-review channel and build voice room
```

### 📁 Channel Management

```
!create a social category with general-gaming-memes channels
!add a creative-corner channel in the social section
!rename general-chat to lounge
!delete the old-announcements channel
!convert active-projects to a forum
```

### 👥 Role Management

```
!create a Scholar role with blue color and mentionable
!give @John the Scholar role
!make a Streak Master role for 7-day study streaks
!set Builder role to be hoisted and pink
```

### 🔧 Maintenance

```
!archive inactive projects
!show me what roles need cleanup
!check study plan progress
```

---

## 📁 Project Structure

```
Bot/
├── docker-compose.yml              # One-command deploy for all services
├── .env.example                    # Environment config template
├── .gitignore
├── README.md                       # ← You are here
│
├── discord-bot/                    # Discord Bot (Python + discord.py)
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── config.yaml                 # Bot config (safety, execution, LLM)
│   ├── prompts/
│   │   └── system_prompt.md        # Local LLM fallback prompt
│   └── bot/
│       ├── __init__.py
│       ├── core.py                 # Main bot class, command handler, UI
│       ├── models.py               # All Pydantic data models
│       ├── utils.py                # Config loading, color parsing, chunking
│       ├── llm_client.py           # Hermes API client + local OpenRouter fallback
│       ├── executor.py             # Action execution engine with safety checks
│       └── actions/
│           ├── __init__.py
│           ├── channels.py         # Channel/forum/voice CRUD
│           └── roles.py            # Role CRUD with protection
│
└── hermes-planner/                 # Hermes Planner API (Python + FastAPI)
    ├── Dockerfile
    ├── requirements.txt
    ├── main.py                     # FastAPI entry point with /plan endpoint
    ├── planner.py                  # LLM orchestration + context enrichment
    ├── context_store.py            # Redis-backed persistence layer
    ├── models.py                   # Shared Pydantic models
    └── prompts/
        └── planner_system.md       # Strategic planning system prompt
```

---

## 🛡️ Safety System

| Protection | How It Works |
|-----------|--------------|
| **Protected Roles** | `@Owner`, `@Admin` — never modified, deleted, or renamed |
| **Protected Channels** | `#rules-and-info`, `#announcements` — never deleted |
| **Confirmation Gate** | Destructive actions (delete, permission changes) require button confirmation |
| **Dry-Run Preview** | Every command shows a preview before any action is taken |
| **Action Limit** | Max 20 actions per prompt (configurable in `config.yaml`) |
| **Error Isolation** | If one action fails, the rest continue — partial success is reported |
| **Authorization** | Only users listed in `ADMIN_USER_IDS` can control the bot |
| **Channel Restriction** | Optionally limit commands to specific channels via `COMMAND_CHANNEL_IDS` |

---

## ⚙️ Configuration Reference

### `discord-bot/config.yaml`

| Section | Key | Default | Description |
|---------|-----|---------|-------------|
| `bot` | `prefix` | `!` | Command prefix |
| `bot` | `status` | 🛠️ Hermes-linked admin | Bot playing status |
| `llm` | `temperature` | `0.1` | LLM creativity (0.0 = deterministic) |
| `llm` | `max_tokens` | `4000` | Max response length |
| `execution` | `confirm_destructive` | `true` | Require confirmation for destructive actions |
| `execution` | `max_actions_per_prompt` | `20` | Max actions per command |
| `safety` | `protected_roles` | `["👑 Owner", "🛡️ Admin"]` | Roles the bot never touches |
| `safety` | `protected_channels` | `["#rules-and-info", "#announcements"]` | Channels the bot never deletes |
| `hermes` | `planner_url` | `http://hermes-planner:8000` | Hermes Planner API URL |
| `hermes` | `fallback_to_local` | `true` | Fall back to direct OpenRouter if Hermes is down |

### `.env` Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `DISCORD_TOKEN` | ✅ | Discord bot token from Developer Portal |
| `OPENROUTER_API_KEY` | ✅ | OpenRouter API key |
| `GUILD_ID` | ✅ | Target Discord server ID |
| `ADMIN_USER_IDS` | ✅ | Comma-separated Discord user IDs (admins) |
| `OPENROUTER_MODEL` | ❌ | LLM model (default: `anthropic/claude-sonnet-4-20250514`) |
| `COMMAND_CHANNEL_IDS` | ❌ | Restrict commands to specific channel IDs |
| `HERMES_MODULE` | ❌ | Your course/module code (for context) |
| `HERMES_EXAM_DATE` | ❌ | ISO 8601 exam date (for context) |
| `HERMES_STUDY_HOURS` | ❌ | Daily study hours (default: 14) |
| `HERMES_TIMEZONE` | ❌ | Your timezone |
| `LOG_LEVEL` | ❌ | Logging level (default: `INFO`) |

---

## 🔧 Operations

### Viewing Logs

```bash
# Discord bot
docker-compose logs -f discord-bot

# Hermes Planner
docker-compose logs -f hermes-planner

# All services
docker-compose logs -f
```

### Restarting

```bash
# Restart a single service
docker-compose restart discord-bot

# Full restart
docker-compose down && docker-compose up -d
```

### Updating

```bash
git pull
docker-compose up -d --build
```

### Data Persistence

All context data (server state, decisions, study plans) is stored in a Docker volume:

```bash
docker volume inspect bot_redis_data
```

To reset all stored context:
```bash
docker-compose down -v && docker-compose up -d
```

---

## 🧪 Testing the Bot

After deployment, test these scenarios:

```bash
# 1. Basic health
curl http://localhost:8000/health
# → {"status":"ok","service":"hermes-planner","version":"1.0.0"}

# 2. In Discord:
!create a test-channel in the General category
```

Expected results:

| Command | Expected Outcome |
|---------|-----------------|
| `!create a test text channel` | Bot replies with preview, shows Execute/Cancel buttons |
| `!make a role called Test-Role with color #ff0000` | Role created, bot confirms |
| `!give @User Test-Role` | Role assigned to user |
| `!delete test-channel` | ⚠️ Destructive action — requires confirmation |
| `!restructure for  exam` | Creates exam cram channels, voice rooms, schedules |

---

## ❓ Troubleshooting

| Symptom | Cause | Solution |
|---------|-------|----------|
| Bot doesn't respond | Wrong `ADMIN_USER_IDS` | Check your Discord ID matches the env var |
| Bot says "Not authorized" | User not in admin list | Add user ID to `ADMIN_USER_IDS` |
| "Target guild not found" | Wrong `GUILD_ID` | Right-click server → Copy ID |
| Planner returns 502 | OpenRouter down or invalid key | Check `OPENROUTER_API_KEY` |
| Planner returns 504 | LLM model timeout | Try a faster model or increase timeout |
| Permissions error on execute | Bot missing Discord permissions | Re-invite with `Administrator` |
| Actions preview says "dry run" | Normal — this is the safety preview | Click Execute to confirm |
| "Protected role/channel" error | You tried to delete a safe item | That's by design — use Discord UI for protected items |
| Redis connection error | Redis not healthy | `docker-compose logs redis` |
| Docker build fails | Python dependencies | Check `docker-compose build --no-cache` |

---

## 🔒 Security Best Practices

1. **Remove `Administrator` after initial setup** — use only the minimum permissions listed above
2. **Keep your `.env` secret** — never commit it, add to `.gitignore` (already done)
3. **Use a dedicated bot account** — never use your personal Discord token
4. **Set `COMMAND_CHANNEL_IDS`** — restrict bot commands to a private admin channel
5. **Review the decision log** — check `docker-compose exec redis redis-cli lrange hermes:{guild_id}:decisions 0 -1`
6. **Regularly audit roles** — ensure @Scholar/@Builder are earned, not just handed out

---

## 🤝 Community & Support

- **GitHub Issues**: [Report bugs](https://github.com/HAliveKP/Bot/issues) or request features
- **Pull Requests**: Contributions welcome — please open an issue first
- **Discord**: Join our [support server](https://discord.gg/your-invite) *(link TBD)*

---

## 📄 License

This project is licensed under the **MIT License** — see the [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgements

- **[discord.py](https://github.com/Rapptz/discord.py)** — Python Discord API wrapper
- **[FastAPI](https://fastapi.tiangolo.com/)** — Modern Python web framework
- **[OpenRouter](https://openrouter.ai/)** — Unified LLM API gateway
- **[Redis](https://redis.io/)** — In-memory data store for context persistence
- **[Docker](https://docker.com/)** — Containerisation platform

---

<div align="center">



*[HAliveKP/Bot](https://github.com/HAliveKP/Bot)*

</div>
