# Deployment Notes

## Fixed Issues

### 1. Anthropic/Claude `top_p` Parameter Error

**Problem**: Anthropic's Claude models don't support having both `temperature` and `top_p` set simultaneously.

**Error**: 
```
litellm.BadRequestError: AnthropicException - 
"`temperature` and `top_p` cannot both be specified for this model. Please use only one."
```

**Solution**: 
1. Updated `modules/llm_client.py` to conditionally include `top_p` only when it's not the default value (1.0)
2. Removed `top_p` from the Claude model config in `config.local.json`

**Code change**:
```python
# Only include top_p if it's not the default (1.0)
# Some models (Anthropic) don't support both temperature and top_p
if mcfg.top_p != 1.0:
    kwargs["top_p"] = mcfg.top_p
```

### 2. Workspace Permissions

**Problem**: Container running as non-root user `critique` couldn't write to `~/prose-critique/workspace/` directories on alma.

**Error**: Permission denied when trying to create log files or save run results.

**Solution**: 
```bash
ssh alma 'chmod -R a+w ~/prose-critique/workspace/'
```

### 3. Web UI Static Files

**Problem**: Flask Blueprint couldn't find static files (CSS/JS).

**Error**: `BuildError: Could not build url for endpoint 'main.static'`

**Solution**: Added `static_folder` and `static_url_path` to Blueprint definition in `web/app.py`:
```python
bp = Blueprint(
    "main", __name__,
    static_folder=str(Path(__file__).parent / "static"),
    static_url_path="/static",
)
```

## Current Configuration

### On alma (http://alma:8020)

- **Primary model**: `claude-sonnet-4.5` (via LiteLLM at http://alma:4000)
- **Audit model**: `gpt-4o-mini` (via LiteLLM at http://alma:4000)
- **Provider**: LiteLLM
- **Audit enabled**: Yes
- **Cache enabled**: No (recommended for production with unique texts)

### Config file location on alma
- Main config: `~/prose-critique/config.json`
- Workspace: `~/prose-critique/workspace/` (logs, runs, cache)
- Service file: `~/.config/systemd/user/prose-critique.service`

## Model Provider Compatibility

### OpenAI (gpt-4o, gpt-4o-mini, etc.)
- ✅ Supports both `temperature` and `top_p`
- ✅ Both parameters can be set simultaneously
- Default: `temperature=0.3, top_p=1.0`

### Anthropic (claude-sonnet-4.5, claude-opus, etc.)
- ⚠️ **Cannot** have both `temperature` and `top_p` set
- ✅ Use `temperature` only
- Config: Omit `top_p` or set it to the default (1.0) - the client will skip sending it

### Google (gemini-pro, etc.)
- ✅ Supports both `temperature` and `top_p`
- Default: `temperature=0.3, top_p=1.0`

## Deployment Commands

```bash
# Update config on alma
scp config.local.json alma:~/prose-critique/config.json

# Restart service
ssh alma 'systemctl --user restart prose-critique.service'

# Check status
make deploy-status

# View logs
make deploy-logs

# Full redeploy (build + transfer + restart)
make deploy
```

## Performance & Timeouts

### Claude-sonnet-4.5 Response Times

Claude-sonnet-4.5 is a very capable model but can be **slower** than OpenAI models, especially for:
- **Russian text** (non-English requires more tokens)
- **Long JSON outputs** (structured critique reports are ~4-8K tokens)
- **Complex analysis** (detailed critique with quotes and evidence)

**Observed timings**:
- Short English text (~300 words): 30-60 seconds
- Medium Russian text (~400 words): **5-7 minutes** ⚠️
- Audit pass (gpt-4o-mini): 30-90 seconds

### Timeout Configuration

If you see `Request timed out` errors in logs:

```bash
ssh alma 'tail -50 ~/prose-critique/workspace/logs/RUNID.log'
```

**Current settings** (updated to handle slow Claude responses):
- **Primary timeout**: 420 seconds (7 minutes)
- **Audit timeout**: 180 seconds (3 minutes)
- **Retries**: 2 attempts each

**To adjust**:
```json
{
  "models": {
    "primary": {
      "timeout": 420,  // Increase if Claude still times out
      "retries": 2
    }
  }
}
```

### Cost Considerations

**Each timeout counts as a failed API call** but still incurs charges:
- Claude-sonnet-4.5: ~$0.50-1.00 per analysis (depending on text length)
- Timeout = charged but no result returned
- 3 retries on 2500-char Russian text ≈ **$3 wasted** if all timeout

**Recommendations**:
1. ✅ Start with shorter texts (~500-1000 chars) to test
2. ✅ Monitor logs during first run: `make deploy-logs`
3. ⚠️ If >5 min wait, consider switching primary to `gpt-4o` (faster, similar quality)
4. ⚠️ For bulk analysis, use `gpt-4o-mini` for primary (10x cheaper, 5x faster)

## Troubleshooting

### Check if service is running
```bash
ssh alma 'systemctl --user status prose-critique.service'
```

### View recent logs
```bash
ssh alma 'podman logs prose-critique | tail -50'
```

### Check workspace permissions
```bash
ssh alma 'ls -la ~/prose-critique/workspace/'
```

### Test web UI
```bash
curl http://alma:8020/api/config
```

### Verify LiteLLM is accessible
```bash
curl http://alma:4000/health
```
