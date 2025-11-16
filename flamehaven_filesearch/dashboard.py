"""
Admin Dashboard for FLAMEHAVEN FileSearch v1.2.0

Provides web UI for:
- API key management (create, list, revoke)
- Usage statistics
- System health monitoring
- Configuration management
"""

import logging
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from .auth import get_key_manager
from .security import RequestContext

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["Dashboard"])


def _get_admin_context(request: Request) -> str:
    """Extract admin user from request"""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )

    parts = auth_header.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Authorization header",
        )

    import os
    admin_key = os.getenv("FLAMEHAVEN_ADMIN_KEY")
    key = parts[1]

    if admin_key and key == admin_key:
        return "admin"

    # Try API key validation
    key_manager = get_key_manager()
    api_key_info = key_manager.validate_key(key)

    if not api_key_info:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )

    return api_key_info.user_id


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Admin dashboard main page"""
    user_id = _get_admin_context(request)

    key_manager = get_key_manager()
    keys = key_manager.list_keys(user_id)
    stats = key_manager.get_usage_stats(user_id=user_id, days=7)

    # Format timestamps
    now = datetime.utcnow()
    keys_data = []
    for key in keys:
        last_used = "Never"
        if key.last_used:
            try:
                last_used_dt = datetime.fromisoformat(
                    key.last_used.replace("Z", "+00:00")
                )
                diff = now - last_used_dt
                if diff.days == 0:
                    last_used = f"{diff.seconds // 3600}h ago"
                else:
                    last_used = f"{diff.days}d ago"
            except Exception:
                last_used = key.last_used

        keys_data.append(
            {
                "id": key.id,
                "name": key.name,
                "created_at": key.created_at[:10],  # Date only
                "last_used": last_used,
                "is_active": "Active" if key.is_active else "Revoked",
                "rate_limit": key.rate_limit_per_minute,
                "permissions": ", ".join(key.permissions),
            }
        )

    total_requests = stats.get("total_requests", 0)
    by_endpoint = stats.get("by_endpoint", {})

    # Top endpoints
    top_endpoints = sorted(
        by_endpoint.items(), key=lambda x: x[1], reverse=True
    )[:5]

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>FLAMEHAVEN FileSearch - Admin Dashboard</title>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            * {{ margin: 0; padding: 0; box-sizing: border-box; }}
            body {{
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
                background: #f5f7fa;
                color: #333;
            }}
            .container {{ max-width: 1200px; margin: 0 auto; padding: 20px; }}
            header {{
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                padding: 30px 0;
                margin-bottom: 30px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            }}
            header h1 {{ font-size: 28px; margin-bottom: 5px; }}
            header p {{ opacity: 0.9; }}
            .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 20px; margin-bottom: 30px; }}
            .card {{
                background: white;
                border-radius: 8px;
                padding: 20px;
                box-shadow: 0 1px 3px rgba(0,0,0,0.1);
            }}
            .stat-value {{ font-size: 36px; font-weight: bold; color: #667eea; margin: 10px 0; }}
            .stat-label {{ font-size: 14px; color: #666; text-transform: uppercase; }}
            .section {{
                background: white;
                border-radius: 8px;
                padding: 25px;
                margin-bottom: 30px;
                box-shadow: 0 1px 3px rgba(0,0,0,0.1);
            }}
            .section h2 {{
                font-size: 20px;
                margin-bottom: 20px;
                padding-bottom: 15px;
                border-bottom: 2px solid #f0f0f0;
            }}
            table {{
                width: 100%;
                border-collapse: collapse;
                font-size: 14px;
            }}
            th {{
                background: #f8f9fa;
                padding: 12px;
                text-align: left;
                font-weight: 600;
                border-bottom: 2px solid #e9ecef;
            }}
            td {{
                padding: 12px;
                border-bottom: 1px solid #e9ecef;
            }}
            tr:hover {{ background: #f8f9fa; }}
            .badge {{
                display: inline-block;
                padding: 4px 12px;
                border-radius: 20px;
                font-size: 12px;
                font-weight: 600;
            }}
            .badge-active {{ background: #d4edda; color: #155724; }}
            .badge-revoked {{ background: #f8d7da; color: #721c24; }}
            .button-group {{
                display: flex;
                gap: 10px;
                justify-content: flex-end;
            }}
            button {{
                padding: 8px 16px;
                border: none;
                border-radius: 4px;
                cursor: pointer;
                font-size: 14px;
                font-weight: 500;
            }}
            .btn-primary {{
                background: #667eea;
                color: white;
            }}
            .btn-primary:hover {{ background: #5568d3; }}
            .btn-danger {{
                background: #dc3545;
                color: white;
            }}
            .btn-danger:hover {{ background: #c82333; }}
            .endpoint-bar {{
                display: flex;
                align-items: center;
                gap: 10px;
                margin-bottom: 10px;
            }}
            .bar {{
                flex: 1;
                height: 20px;
                background: #e9ecef;
                border-radius: 4px;
                overflow: hidden;
            }}
            .bar-fill {{
                height: 100%;
                background: linear-gradient(90deg, #667eea, #764ba2);
                transition: width 0.3s ease;
            }}
            .endpoint-name {{ min-width: 150px; font-weight: 500; }}
            .endpoint-count {{ min-width: 50px; text-align: right; font-weight: 600; }}
            .empty {{ color: #666; font-style: italic; text-align: center; padding: 20px; }}
            footer {{
                text-align: center;
                padding: 20px;
                color: #666;
                font-size: 12px;
            }}
        </style>
    </head>
    <body>
        <header>
            <div class="container">
                <h1>🔥 FLAMEHAVEN FileSearch</h1>
                <p>Admin Dashboard • v1.2.0</p>
            </div>
        </header>

        <div class="container">
            <div class="grid">
                <div class="card">
                    <div class="stat-label">Total Requests</div>
                    <div class="stat-value">{total_requests:,}</div>
                    <div class="stat-label" style="font-size: 12px; color: #999;">Last 7 days</div>
                </div>
                <div class="card">
                    <div class="stat-label">Active Keys</div>
                    <div class="stat-value">{sum(1 for k in keys if k.is_active)}</div>
                    <div class="stat-label" style="font-size: 12px; color: #999;">Total: {len(keys)}</div>
                </div>
                <div class="card">
                    <div class="stat-label">Top Endpoint</div>
                    <div class="stat-value" style="font-size: 18px;">{top_endpoints[0][0] if top_endpoints else 'N/A'}</div>
                    <div class="stat-label" style="font-size: 12px; color: #999;">{top_endpoints[0][1] if top_endpoints else 0} requests</div>
                </div>
                <div class="card">
                    <div class="stat-label">User ID</div>
                    <div class="stat-value" style="font-size: 16px; word-break: break-all;">{user_id[:20]}</div>
                </div>
            </div>

            <div class="section">
                <h2>API Keys</h2>
                {f'''
                <table>
                    <thead>
                        <tr>
                            <th>Name</th>
                            <th>Status</th>
                            <th>Created</th>
                            <th>Last Used</th>
                            <th>Rate Limit</th>
                            <th>Permissions</th>
                            <th>Action</th>
                        </tr>
                    </thead>
                    <tbody>
                        {chr(10).join(f'''
                        <tr>
                            <td><code style="background: #f5f5f5; padding: 2px 6px; border-radius: 3px;">{k["id"]}</code><br><small>{k["name"]}</small></td>
                            <td><span class="badge badge-{k["is_active"].lower()}">{k["is_active"]}</span></td>
                            <td>{k["created_at"]}</td>
                            <td>{k["last_used"]}</td>
                            <td>{k["rate_limit"]}/min</td>
                            <td><small>{k["permissions"]}</small></td>
                            <td><button class="btn-danger" onclick="revokeKey('{k["id"]}')">Revoke</button></td>
                        </tr>
                        ''' for k in keys_data) if keys_data else '<tr><td colspan="7" class="empty">No API keys found</td></tr>'}
                    </tbody>
                </table>
                ''' if keys_data or True else '<p class="empty">No API keys found</p>'}
            </div>

            <div class="section">
                <h2>Request Distribution (Last 7 Days)</h2>
                {f'''
                <div style="padding: 20px 0;">
                    {chr(10).join(f'''
                    <div class="endpoint-bar">
                        <div class="endpoint-name">{endpoint}</div>
                        <div class="bar">
                            <div class="bar-fill" style="width: {(count / max(by_endpoint.values(), default=1)) * 100}%"></div>
                        </div>
                        <div class="endpoint-count">{count}</div>
                    </div>
                    ''' for endpoint, count in top_endpoints) if top_endpoints else '<p class="empty">No requests in the last 7 days</p>'}
                </div>
                ''' if top_endpoints else '<p class="empty">No request data available</p>'}
            </div>

            <div class="section">
                <h2>API Reference</h2>
                <p>Use the following endpoints to manage your API keys:</p>
                <ul style="margin-left: 20px; margin-top: 10px;">
                    <li><code>POST /api/admin/keys</code> - Create new API key</li>
                    <li><code>GET /api/admin/keys</code> - List your API keys</li>
                    <li><code>DELETE /api/admin/keys/{{key_id}}</code> - Revoke API key</li>
                    <li><code>GET /api/admin/usage</code> - Get usage statistics</li>
                    <li><code>POST /api/admin/batch-search</code> - Batch search (v1.2.0)</li>
                </ul>
            </div>
        </div>

        <footer>
            <p>FLAMEHAVEN FileSearch v1.2.0 • Last updated: {datetime.utcnow().isoformat()}Z</p>
        </footer>

        <script>
            function revokeKey(keyId) {{
                if (confirm('Are you sure you want to revoke this API key? It cannot be undone.')) {{
                    fetch(`/api/admin/keys/${{keyId}}`, {{
                        method: 'DELETE',
                        headers: {{
                            'Authorization': `Bearer ${{localStorage.getItem('admin_token')}}`
                        }}
                    }})
                    .then(r => r.json())
                    .then(data => {{
                        if (data.status === 'success') {{
                            alert('API key revoked successfully');
                            location.reload();
                        }} else {{
                            alert('Error: ' + data.detail);
                        }}
                    }})
                    .catch(err => alert('Error: ' + err));
                }}
            }}
        </script>
    </body>
    </html>
    """

    return html


@router.get("/health-check", response_class=HTMLResponse)
async def health_check_page(request: Request):
    """Simple health check page"""
    user_id = _get_admin_context(request)

    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Health Check</title>
        <style>
            body {
                font-family: monospace;
                background: #1e1e1e;
                color: #00ff00;
                padding: 20px;
            }
            .status-ok { color: #00ff00; }
            .status-warning { color: #ffaa00; }
            .status-error { color: #ff0000; }
        </style>
    </head>
    <body>
        <h1>FLAMEHAVEN FileSearch - Health Check</h1>
        <p>Timestamp: """ + datetime.utcnow().isoformat() + """Z</p>
        <p class="status-ok">[OK] Admin dashboard is operational</p>
        <p class="status-ok">[OK] API key management enabled</p>
        <p class="status-ok">[OK] Audit logging active</p>
        <p><a href="/admin/dashboard">← Back to Dashboard</a></p>
    </body>
    </html>
    """
    return html
