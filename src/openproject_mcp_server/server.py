#!/usr/bin/env python3
"""
OpenProject MCP Server using FastMCP

A Model Context Protocol (MCP) server built with FastMCP that provides
integration with OpenProject API v3.
"""

import os
import logging
import json
from typing import Optional
from dotenv import load_dotenv
from fastmcp import FastMCP

# Import OpenProject client from existing module
from . import OpenProjectClient, __version__

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Initialize FastMCP server
mcp = FastMCP("OpenProject MCP Server")

# Global client instance
client: Optional[OpenProjectClient] = None


async def get_client() -> OpenProjectClient:
    """Get or create OpenProject client"""
    global client
    if client is None:
        base_url = os.getenv("OPENPROJECT_URL")
        api_key = os.getenv("OPENPROJECT_API_KEY")
        proxy = os.getenv("OPENPROJECT_PROXY")
        
        if not base_url or not api_key:
            raise ValueError("OPENPROJECT_URL and OPENPROJECT_API_KEY must be set")
        
        client = OpenProjectClient(base_url, api_key, proxy)
        logger.info(f"✅ OpenProject Client initialized for {base_url}")
        
        # Optional: Test connection on startup
        if os.getenv("TEST_CONNECTION_ON_STARTUP", "false").lower() == "true":
            try:
                await client.test_connection()
                logger.info("✅ API connection test successful!")
            except Exception as e:
                logger.error(f"❌ API connection test failed: {e}")
    
    return client


# ============================================================================
# MCP Tools - Connection & Testing
# ============================================================================

@mcp.tool()
async def test_connection() -> str:
    """Test the connection to the OpenProject API"""
    try:
        c = await get_client()
        result = await c.test_connection()
        
        if result.get("instanceName"):
            return f"✅ Connected to: {result['instanceName']}\n" \
                   f"Core Version: {result.get('coreVersion', 'Unknown')}"
        return "✅ Connection successful!"
    except Exception as e:
        return f"❌ Connection failed: {str(e)}"


# ============================================================================
# MCP Tools - Projects
# ============================================================================

@mcp.tool()
async def list_projects(active_only: bool = True) -> str:
    """
    List all OpenProject projects
    
    Args:
        active_only: Show only active projects (default: True)
    """
    try:
        c = await get_client()
        
        # Build filters for active_only
        filters = None
        if active_only:
            filters = json.dumps([{"active": {"operator": "=", "values": ["t"]}}])
        
        result = await c.get_projects(filters=filters)
        
        projects = result.get("_embedded", {}).get("elements", [])
        
        if not projects:
            return "No projects found."
        
        text = f"📋 Projects ({len(projects)} found):\n\n"
        for project in projects:
            status = "🟢" if project.get("active", False) else "🔴"
            text += f"{status} **{project['name']}** (ID: {project['id']})\n"
            if project.get("description", {}).get("raw"):
                desc = project["description"]["raw"][:100]
                text += f"   {desc}{'...' if len(project['description']['raw']) > 100 else ''}\n"
        
        return text
    except Exception as e:
        logger.error(f"Error listing projects: {e}", exc_info=True)
        return f"❌ Error: {str(e)}"


@mcp.tool()
async def get_project(project_id: int) -> str:
    """
    Get detailed information about a specific project
    
    Args:
        project_id: The project ID
    """
    try:
        c = await get_client()
        project = await c.get_project(project_id)
        
        text = f"📋 **{project['name']}**\n\n"
        text += f"- **ID**: {project['id']}\n"
        text += f"- **Identifier**: {project.get('identifier', 'N/A')}\n"
        text += f"- **Status**: {'🟢 Active' if project.get('active', False) else '🔴 Archived'}\n"
        text += f"- **Public**: {'Yes' if project.get('public', False) else 'No'}\n"
        
        if project.get("description", {}).get("raw"):
            text += f"\n**Description**:\n{project['description']['raw']}\n"
        
        return text
    except Exception as e:
        logger.error(f"Error getting project: {e}", exc_info=True)
        return f"❌ Error: {str(e)}"


@mcp.tool()
async def create_project(
    name: str,
    identifier: str,
    description: Optional[str] = None,
    public: bool = False,
    status: Optional[str] = None,
    parent_id: Optional[int] = None
) -> str:
    """
    Create a new project
    
    Args:
        name: Project name
        identifier: Project identifier (unique, lowercase, no spaces)
        description: Project description (optional)
        public: Whether the project is public (default: False)
        status: Project status (optional)
        parent_id: Parent project ID (optional)
    """
    try:
        c = await get_client()
        data = {
            "name": name,
            "identifier": identifier,
            "public": public
        }
        if description:
            data["description"] = description
        if status:
            data["status"] = status
        if parent_id:
            data["parent_id"] = parent_id
        
        project = await c.create_project(data)
        return f"✅ Project created: **{project['name']}** (ID: {project['id']})"
    except Exception as e:
        logger.error(f"Error creating project: {e}", exc_info=True)
        return f"❌ Error: {str(e)}"


# ============================================================================
# MCP Tools - Work Packages
# ============================================================================

@mcp.tool()
async def list_work_packages(
    project_id: Optional[int] = None,
    status: str = "open",
    offset: Optional[int] = None,
    page_size: Optional[int] = None
) -> str:
    """
    List work packages with optional filtering
    
    Args:
        project_id: Filter by project ID (optional)
        status: Status filter - "open", "closed", or "all" (default: "open")
        offset: Starting index for pagination (optional)
        page_size: Number of results per page (optional, max: 100)
    """
    try:
        c = await get_client()
        
        # Build filters based on status
        import json
        filters = []
        if status == "open":
            filters.append({"status": {"operator": "o", "values": []}})
        elif status == "closed":
            filters.append({"status": {"operator": "c", "values": []}})
        # "all" means no status filter
        
        filters_str = json.dumps(filters) if filters else None
        
        result = await c.get_work_packages(
            project_id=project_id,
            filters=filters_str,
            offset=offset,
            page_size=page_size
        )
        
        work_packages = result.get("_embedded", {}).get("elements", [])
        
        if not work_packages:
            return "No work packages found."
        
        total = result.get("total", len(work_packages))
        text = f"📝 Work Packages ({len(work_packages)} of {total}):\n\n"
        
        for wp in work_packages:
            status_name = wp.get("_embedded", {}).get("status", {}).get("name", "Unknown")
            text += f"#{wp['id']} - **{wp['subject']}**\n"
            text += f"   Status: {status_name}\n"
            
            wp_type = wp.get("_embedded", {}).get("type", {}).get("name", "N/A")
            text += f"   Type: {wp_type}\n"
            
            if wp.get("_embedded", {}).get("assignee"):
                assignee = wp["_embedded"]["assignee"].get("name", "N/A")
                text += f"   Assignee: {assignee}\n"
            
            text += "\n"
        
        return text
    except Exception as e:
        logger.error(f"Error listing work packages: {e}", exc_info=True)
        return f"❌ Error: {str(e)}"


@mcp.tool()
async def get_work_package(work_package_id: int) -> str:
    """
    Get detailed information about a specific work package
    
    Args:
        work_package_id: The work package ID
    """
    try:
        c = await get_client()
        wp = await c.get_work_package(work_package_id)
        
        text = f"📝 #{wp['id']} - **{wp['subject']}**\n\n"
        
        status = wp.get("_embedded", {}).get("status", {}).get("name", "Unknown")
        text += f"- **Status**: {status}\n"
        
        wp_type = wp.get("_embedded", {}).get("type", {}).get("name", "N/A")
        text += f"- **Type**: {wp_type}\n"
        
        if wp.get("_embedded", {}).get("priority"):
            priority = wp["_embedded"]["priority"].get("name", "N/A")
            text += f"- **Priority**: {priority}\n"
        
        if wp.get("_embedded", {}).get("assignee"):
            assignee = wp["_embedded"]["assignee"].get("name", "Unassigned")
            text += f"- **Assignee**: {assignee}\n"
        
        if wp.get("_embedded", {}).get("project"):
            project = wp["_embedded"]["project"].get("name", "N/A")
            text += f"- **Project**: {project}\n"
        
        if wp.get("description", {}).get("raw"):
            text += f"\n**Description**:\n{wp['description']['raw']}\n"
        
        return text
    except Exception as e:
        logger.error(f"Error getting work package: {e}", exc_info=True)
        return f"❌ Error: {str(e)}"


@mcp.tool()
async def create_work_package(
    project_id: int,
    subject: str,
    type_id: int,
    description: Optional[str] = None,
    priority_id: Optional[int] = None,
    assignee_id: Optional[int] = None
) -> str:
    """
    Create a new work package
    
    Args:
        project_id: The project ID
        subject: Work package title
        type_id: Type ID (e.g., 1 for Task)
        description: Description in Markdown format (optional)
        priority_id: Priority ID (optional)
        assignee_id: User ID to assign to (optional)
    """
    try:
        c = await get_client()
        # OpenProjectClient expects 'project' and 'type' keys, not 'project_id' and 'type_id'
        data = {
            "project": project_id,
            "subject": subject,
            "type": type_id
        }
        if description:
            data["description"] = description
        if priority_id:
            data["priority_id"] = priority_id
        if assignee_id:
            data["assignee_id"] = assignee_id
        
        wp = await c.create_work_package(data)
        return f"✅ Work package created: #{wp['id']} - **{wp['subject']}**"
    except Exception as e:
        logger.error(f"Error creating work package: {e}", exc_info=True)
        return f"❌ Error: {str(e)}"


@mcp.tool()
async def update_work_package(
    work_package_id: int,
    subject: Optional[str] = None,
    description: Optional[str] = None,
    type_id: Optional[int] = None,
    status_id: Optional[int] = None,
    priority_id: Optional[int] = None,
    assignee_id: Optional[int] = None,
    percentage_done: Optional[int] = None
) -> str:
    """
    Update an existing work package
    
    Args:
        work_package_id: The work package ID
        subject: Work package title (optional)
        description: Description in Markdown format (optional)
        type_id: Type ID (optional)
        status_id: Status ID (optional)
        priority_id: Priority ID (optional)
        assignee_id: User ID to assign to (optional)
        percentage_done: Completion percentage 0-100 (optional)
    """
    try:
        c = await get_client()
        data = {}
        if subject is not None:
            data["subject"] = subject
        if description is not None:
            data["description"] = description
        if type_id is not None:
            data["type_id"] = type_id
        if status_id is not None:
            data["status_id"] = status_id
        if priority_id is not None:
            data["priority_id"] = priority_id
        if assignee_id is not None:
            data["assignee_id"] = assignee_id
        if percentage_done is not None:
            data["percentage_done"] = percentage_done
        
        wp = await c.update_work_package(work_package_id, data)
        return f"✅ Work package updated: #{wp['id']} - **{wp['subject']}**"
    except Exception as e:
        logger.error(f"Error updating work package: {e}", exc_info=True)
        return f"❌ Error: {str(e)}"


@mcp.tool()
async def delete_work_package(work_package_id: int) -> str:
    """
    Delete a work package
    
    Args:
        work_package_id: The work package ID
    """
    try:
        c = await get_client()
        await c.delete_work_package(work_package_id)
        return f"✅ Work package #{work_package_id} deleted successfully"
    except Exception as e:
        logger.error(f"Error deleting work package: {e}", exc_info=True)
        return f"❌ Error: {str(e)}"


@mcp.tool()
async def list_types(project_id: Optional[int] = None) -> str:
    """
    List available work package types
    
    Args:
        project_id: Filter types by project (optional)
    """
    try:
        c = await get_client()
        result = await c.get_types(project_id=project_id)
        
        types = result.get("_embedded", {}).get("elements", [])
        
        if not types:
            return "No types found."
        
        text = f"🏷️  Work Package Types ({len(types)}):\n\n"
        for t in types:
            text += f"- **{t['name']}** (ID: {t['id']})\n"
        
        return text
    except Exception as e:
        logger.error(f"Error listing types: {e}", exc_info=True)
        return f"❌ Error: {str(e)}"


# Add remaining tools following the same pattern...
# For brevity, I'll add a few more key ones

@mcp.tool()
async def list_users(active_only: bool = True) -> str:
    """
    List all users in the OpenProject instance
    
    Args:
        active_only: Show only active users (default: True)
    """
    try:
        c = await get_client()
        import json
        filters = None
        if active_only:
            filters = json.dumps([{"status": {"operator": "=", "values": ["active"]}}])
        result = await c.get_users(filters=filters)
        
        users = result.get("_embedded", {}).get("elements", [])
        
        if not users:
            return "No users found."
        
        text = f"👥 Users ({len(users)} found):\n\n"
        for user in users:
            status = "🟢" if user.get("status") == "active" else "🔴"
            text += f"{status} **{user.get('name', 'N/A')}** (ID: {user['id']})\n"
            if user.get("email"):
                text += f"   📧 {user['email']}\n"
        
        return text
    except Exception as e:
        logger.error(f"Error listing users: {e}", exc_info=True)
        return f"❌ Error: {str(e)}"


@mcp.tool()
async def get_user(user_id: int) -> str:
    """
    Get detailed information about a specific user
    
    Args:
        user_id: The user ID
    """
    try:
        c = await get_client()
        user = await c.get_user(user_id)
        
        text = f"👤 **{user.get('name', 'N/A')}**\n\n"
        text += f"- **ID**: {user['id']}\n"
        text += f"- **Status**: {user.get('status', 'N/A')}\n"
        if user.get("email"):
            text += f"- **Email**: {user['email']}\n"
        if user.get("login"):
            text += f"- **Login**: {user['login']}\n"
        
        return text
    except Exception as e:
        logger.error(f"Error getting user: {e}", exc_info=True)
        return f"❌ Error: {str(e)}"


@mcp.tool()
async def list_statuses() -> str:
    """List all available work package statuses"""
    try:
        c = await get_client()
        result = await c.get_statuses()
        
        statuses = result.get("_embedded", {}).get("elements", [])
        
        if not statuses:
            return "No statuses found."
        
        text = f"📊 Work Package Statuses ({len(statuses)}):\n\n"
        for s in statuses:
            text += f"- **{s['name']}** (ID: {s['id']})\n"
        
        return text
    except Exception as e:
        logger.error(f"Error listing statuses: {e}", exc_info=True)
        return f"❌ Error: {str(e)}"


@mcp.tool()
async def list_priorities() -> str:
    """List all available work package priorities"""
    try:
        c = await get_client()
        result = await c.get_priorities()
        
        priorities = result.get("_embedded", {}).get("elements", [])
        
        if not priorities:
            return "No priorities found."
        
        text = f"⭐ Work Package Priorities ({len(priorities)}):\n\n"
        for p in priorities:
            text += f"- **{p['name']}** (ID: {p['id']})\n"
        
        return text
    except Exception as e:
        logger.error(f"Error listing priorities: {e}", exc_info=True)
        return f"❌ Error: {str(e)}"


@mcp.tool()
async def update_project(
    project_id: int,
    name: Optional[str] = None,
    identifier: Optional[str] = None,
    description: Optional[str] = None,
    public: Optional[bool] = None,
    status: Optional[str] = None,
    parent_id: Optional[int] = None
) -> str:
    """
    Update an existing project
    
    Args:
        project_id: The project ID
        name: Project name (optional)
        identifier: Project identifier (optional)
        description: Project description (optional)
        public: Whether the project is public (optional)
        status: Project status (optional)
        parent_id: Parent project ID (optional)
    """
    try:
        c = await get_client()
        data = {}
        if name is not None:
            data["name"] = name
        if identifier is not None:
            data["identifier"] = identifier
        if description is not None:
            data["description"] = description
        if public is not None:
            data["public"] = public
        if status is not None:
            data["status"] = status
        if parent_id is not None:
            data["parent_id"] = parent_id
        
        project = await c.update_project(project_id, data)
        return f"✅ Project updated: **{project['name']}** (ID: {project['id']})"
    except Exception as e:
        logger.error(f"Error updating project: {e}", exc_info=True)
        return f"❌ Error: {str(e)}"


@mcp.tool()
async def delete_project(project_id: int) -> str:
    """
    Delete a project
    
    Args:
        project_id: The project ID
    """
    try:
        c = await get_client()
        await c.delete_project(project_id)
        return f"✅ Project #{project_id} deleted successfully"
    except Exception as e:
        logger.error(f"Error deleting project: {e}", exc_info=True)
        return f"❌ Error: {str(e)}"


@mcp.tool()
async def list_memberships(
    project_id: Optional[int] = None,
    user_id: Optional[int] = None
) -> str:
    """
    List project memberships
    
    Args:
        project_id: Filter by specific project (optional)
        user_id: Filter by specific user (optional)
    """
    try:
        c = await get_client()
        result = await c.get_memberships(project_id=project_id, user_id=user_id)
        
        memberships = result.get("_embedded", {}).get("elements", [])
        
        if not memberships:
            return "No memberships found."
        
        text = f"👥 Memberships ({len(memberships)} found):\n\n"
        for m in memberships:
            principal = m.get("_embedded", {}).get("principal", {})
            project = m.get("_embedded", {}).get("project", {})
            roles = m.get("_embedded", {}).get("roles", [])
            
            text += f"- **{principal.get('name', 'N/A')}** in **{project.get('name', 'N/A')}**\n"
            text += f"  Roles: {', '.join([r.get('name', 'N/A') for r in roles])}\n"
        
        return text
    except Exception as e:
        logger.error(f"Error listing memberships: {e}", exc_info=True)
        return f"❌ Error: {str(e)}"


@mcp.tool()
async def create_membership(
    project_id: int,
    user_id: Optional[int] = None,
    group_id: Optional[int] = None,
    role_ids: Optional[list[int]] = None,
    role_id: Optional[int] = None
) -> str:
    """
    Create a new project membership
    
    Args:
        project_id: The project ID
        user_id: User ID (required if group_id not provided)
        group_id: Group ID (required if user_id not provided)
        role_ids: Array of role IDs (optional)
        role_id: Single role ID (optional, alternative to role_ids)
    """
    try:
        c = await get_client()
        data = {"project_id": project_id}
        if user_id:
            data["user_id"] = user_id
        elif group_id:
            data["group_id"] = group_id
        else:
            return "❌ Error: Either user_id or group_id must be provided"
        
        if role_ids:
            data["role_ids"] = role_ids
        elif role_id:
            data["role_id"] = role_id
        
        await c.create_membership(data)
        return f"✅ Membership created successfully"
    except Exception as e:
        logger.error(f"Error creating membership: {e}", exc_info=True)
        return f"❌ Error: {str(e)}"


@mcp.tool()
async def update_membership(
    membership_id: int,
    role_ids: Optional[list[int]] = None,
    role_id: Optional[int] = None
) -> str:
    """
    Update an existing membership
    
    Args:
        membership_id: The membership ID
        role_ids: Array of role IDs (optional)
        role_id: Single role ID (optional)
    """
    try:
        c = await get_client()
        data = {}
        if role_ids:
            data["role_ids"] = role_ids
        elif role_id:
            data["role_id"] = role_id
        
        await c.update_membership(membership_id, data)
        return f"✅ Membership #{membership_id} updated successfully"
    except Exception as e:
        logger.error(f"Error updating membership: {e}", exc_info=True)
        return f"❌ Error: {str(e)}"


@mcp.tool()
async def delete_membership(membership_id: int) -> str:
    """
    Delete a membership
    
    Args:
        membership_id: The membership ID
    """
    try:
        c = await get_client()
        await c.delete_membership(membership_id)
        return f"✅ Membership #{membership_id} deleted successfully"
    except Exception as e:
        logger.error(f"Error deleting membership: {e}", exc_info=True)
        return f"❌ Error: {str(e)}"


@mcp.tool()
async def get_membership(membership_id: int) -> str:
    """
    Get detailed information about a specific membership
    
    Args:
        membership_id: The membership ID
    """
    try:
        c = await get_client()
        m = await c.get_membership(membership_id)
        
        principal = m.get("_embedded", {}).get("principal", {})
        project = m.get("_embedded", {}).get("project", {})
        roles = m.get("_embedded", {}).get("roles", [])
        
        text = f"👤 **{principal.get('name', 'N/A')}** in **{project.get('name', 'N/A')}**\n\n"
        text += f"- **Membership ID**: {m['id']}\n"
        text += f"- **Roles**: {', '.join([r.get('name', 'N/A') for r in roles])}\n"
        
        return text
    except Exception as e:
        logger.error(f"Error getting membership: {e}", exc_info=True)
        return f"❌ Error: {str(e)}"


@mcp.tool()
async def list_roles() -> str:
    """List all available roles"""
    try:
        c = await get_client()
        result = await c.get_roles()
        
        roles = result.get("_embedded", {}).get("elements", [])
        
        if not roles:
            return "No roles found."
        
        text = f"🎭 Roles ({len(roles)} found):\n\n"
        for r in roles:
            text += f"- **{r['name']}** (ID: {r['id']})\n"
        
        return text
    except Exception as e:
        logger.error(f"Error listing roles: {e}", exc_info=True)
        return f"❌ Error: {str(e)}"


@mcp.tool()
async def get_role(role_id: int) -> str:
    """
    Get detailed information about a specific role
    
    Args:
        role_id: The role ID
    """
    try:
        c = await get_client()
        role = await c.get_role(role_id)
        
        text = f"🎭 **{role['name']}**\n\n"
        text += f"- **ID**: {role['id']}\n"
        
        return text
    except Exception as e:
        logger.error(f"Error getting role: {e}", exc_info=True)
        return f"❌ Error: {str(e)}"


@mcp.tool()
async def list_time_entry_activities() -> str:
    """
    List all available time entry activities
    
    Returns:
        List of available time entry activities with their IDs and names
    """
    try:
        c = await get_client()
        result = await c.get_time_entry_activities()
        
        if not result.get("_embedded", {}).get("elements"):
            return "No time entry activities found"
        
        text = f"⏱️ **Time Entry Activities** (Total: {result['total']})\n\n"
        
        for activity in result["_embedded"]["elements"]:
            text += f"- **{activity['name']}** (ID: {activity['id']})\n"
            if activity.get('default'):
                text += "  ⭐ Default activity\n"
        
        return text
    except Exception as e:
        logger.error(f"Error listing time entry activities: {e}", exc_info=True)
        return f"❌ Error: {str(e)}"


@mcp.tool()
async def list_time_entries(
    work_package_id: Optional[int] = None,
    user_id: Optional[int] = None
) -> str:
    """
    List time entries with optional filtering
    
    Args:
        work_package_id: Filter by specific work package (optional)
        user_id: Filter by specific user (optional)
    """
    try:
        c = await get_client()
        import json
        filters = []
        if work_package_id:
            filters.append({"work_package_id": {"operator": "=", "values": [str(work_package_id)]}})
        if user_id:
            filters.append({"user_id": {"operator": "=", "values": [str(user_id)]}})
        
        filters_str = json.dumps(filters) if filters else None
        result = await c.get_time_entries(filters=filters_str)
        
        entries = result.get("_embedded", {}).get("elements", [])
        
        if not entries:
            return "No time entries found."
        
        text = f"⏱️  Time Entries ({len(entries)} found):\n\n"
        for te in entries:
            hours = te.get("hours", "PT0H").replace("PT", "").replace("H", "")
            text += f"- **{hours}h** on {te.get('spentOn', 'N/A')}\n"
            if te.get("comment", {}).get("raw"):
                text += f"  {te['comment']['raw'][:50]}...\n"
        
        return text
    except Exception as e:
        logger.error(f"Error listing time entries: {e}", exc_info=True)
        return f"❌ Error: {str(e)}"


@mcp.tool()
async def create_time_entry(
    work_package_id: int,
    hours: float,
    spent_on: str,
    comment: Optional[str] = None,
    activity_id: Optional[int] = None
) -> str:
    """
    Create a new time entry
    
    Args:
        work_package_id: The work package ID
        hours: Hours spent (e.g., 2.5)
        spent_on: Date when time was spent (YYYY-MM-DD format)
        comment: Comment/description (optional)
        activity_id: Activity ID (optional, e.g., 3 for Development)
    """
    try:
        c = await get_client()
        data = {
            "work_package_id": work_package_id,
            "hours": hours,
            "spent_on": spent_on
        }
        if comment:
            data["comment"] = comment
        if activity_id:
            data["activity_id"] = activity_id
        
        await c.create_time_entry(data)
        return f"✅ Time entry created: {hours}h on {spent_on}"
    except Exception as e:
        logger.error(f"Error creating time entry: {e}", exc_info=True)
        return f"❌ Error: {str(e)}"


@mcp.tool()
async def update_time_entry(
    time_entry_id: int,
    hours: Optional[float] = None,
    spent_on: Optional[str] = None,
    comment: Optional[str] = None,
    activity_id: Optional[int] = None
) -> str:
    """
    Update an existing time entry
    
    Args:
        time_entry_id: The time entry ID
        hours: Hours spent (optional)
        spent_on: Date when time was spent (optional)
        comment: Comment/description (optional)
        activity_id: Activity ID (optional)
    """
    try:
        c = await get_client()
        data = {}
        if hours is not None:
            data["hours"] = hours
        if spent_on is not None:
            data["spent_on"] = spent_on
        if comment is not None:
            data["comment"] = comment
        if activity_id is not None:
            data["activity_id"] = activity_id
        
        await c.update_time_entry(time_entry_id, data)
        return f"✅ Time entry #{time_entry_id} updated successfully"
    except Exception as e:
        logger.error(f"Error updating time entry: {e}", exc_info=True)
        return f"❌ Error: {str(e)}"


@mcp.tool()
async def delete_time_entry(time_entry_id: int) -> str:
    """
    Delete a time entry
    
    Args:
        time_entry_id: The time entry ID
    """
    try:
        c = await get_client()
        await c.delete_time_entry(time_entry_id)
        return f"✅ Time entry #{time_entry_id} deleted successfully"
    except Exception as e:
        logger.error(f"Error deleting time entry: {e}", exc_info=True)
        return f"❌ Error: {str(e)}"


@mcp.tool()
async def list_versions(project_id: Optional[int] = None) -> str:
    """
    List project versions/milestones
    
    Args:
        project_id: Filter by specific project (optional)
    """
    try:
        c = await get_client()
        result = await c.get_versions(project_id=project_id)
        
        versions = result.get("_embedded", {}).get("elements", [])
        
        if not versions:
            return "No versions found."
        
        text = f"📦 Versions ({len(versions)} found):\n\n"
        for v in versions:
            text += f"- **{v['name']}** (ID: {v['id']})\n"
            if v.get("startDate") or v.get("endDate"):
                text += f"  {v.get('startDate', '')} → {v.get('endDate', '')}\n"
        
        return text
    except Exception as e:
        logger.error(f"Error listing versions: {e}", exc_info=True)
        return f"❌ Error: {str(e)}"


@mcp.tool()
async def create_version(
    project_id: int,
    name: str,
    description: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    status: Optional[str] = None
) -> str:
    """
    Create a new project version/milestone
    
    Args:
        project_id: The project ID
        name: Version name
        description: Version description (optional)
        start_date: Start date (YYYY-MM-DD format, optional)
        end_date: End date (YYYY-MM-DD format, optional)
        status: Version status (open, locked, closed) (optional)
    """
    try:
        c = await get_client()
        data = {"name": name}
        if description:
            data["description"] = description
        if start_date:
            data["start_date"] = start_date
        if end_date:
            data["end_date"] = end_date
        if status:
            data["status"] = status
        
        await c.create_version(project_id, data)
        return f"✅ Version created: **{name}**"
    except Exception as e:
        logger.error(f"Error creating version: {e}", exc_info=True)
        return f"❌ Error: {str(e)}"


@mcp.tool()
async def set_work_package_parent(work_package_id: int, parent_id: int) -> str:
    """
    Set a parent for a work package (create parent-child relationship)
    
    Args:
        work_package_id: The work package ID to become a child
        parent_id: The work package ID to become the parent
    """
    try:
        c = await get_client()
        await c.set_work_package_parent(work_package_id, parent_id)
        return f"✅ Work package #{work_package_id} is now a child of #{parent_id}"
    except Exception as e:
        logger.error(f"Error setting parent: {e}", exc_info=True)
        return f"❌ Error: {str(e)}"


@mcp.tool()
async def remove_work_package_parent(work_package_id: int) -> str:
    """
    Remove parent relationship from a work package (make it top-level)
    
    Args:
        work_package_id: The work package ID to remove parent from
    """
    try:
        c = await get_client()
        await c.remove_work_package_parent(work_package_id)
        return f"✅ Work package #{work_package_id} is now top-level"
    except Exception as e:
        logger.error(f"Error removing parent: {e}", exc_info=True)
        return f"❌ Error: {str(e)}"


@mcp.tool()
async def list_work_package_children(
    parent_id: int,
    include_descendants: bool = False
) -> str:
    """
    List all child work packages of a parent
    
    Args:
        parent_id: The parent work package ID
        include_descendants: Include grandchildren and all descendants (default: False)
    """
    try:
        c = await get_client()
        result = await c.list_work_package_children(parent_id, include_descendants)
        
        children = result.get("_embedded", {}).get("elements", [])
        
        if not children:
            return f"No children found for work package #{parent_id}."
        
        text = f"👶 Children of #{parent_id} ({len(children)} found):\n\n"
        for wp in children:
            text += f"#{wp['id']} - **{wp['subject']}**\n"
        
        return text
    except Exception as e:
        logger.error(f"Error listing children: {e}", exc_info=True)
        return f"❌ Error: {str(e)}"


@mcp.tool()
async def create_work_package_relation(
    from_id: int,
    to_id: int,
    relation_type: str,
    lag: Optional[int] = None,
    description: Optional[str] = None
) -> str:
    """
    Create a relationship between work packages
    
    Args:
        from_id: Source work package ID
        to_id: Target work package ID
        relation_type: Relation type (blocks, follows, precedes, relates, duplicates, includes, requires, partof)
        lag: Lag in working days (optional, for follows/precedes)
        description: Optional description of the relation
    """
    try:
        c = await get_client()
        data = {
            "from_id": from_id,
            "to_id": to_id,
            "relation_type": relation_type
        }
        if lag is not None:
            data["lag"] = lag
        if description:
            data["description"] = description
        
        await c.create_work_package_relation(data)
        return f"✅ Relation created: #{from_id} {relation_type} #{to_id}"
    except Exception as e:
        logger.error(f"Error creating relation: {e}", exc_info=True)
        return f"❌ Error: {str(e)}"


@mcp.tool()
async def list_work_package_relations(
    work_package_id: Optional[int] = None,
    relation_type: Optional[str] = None
) -> str:
    """
    List work package relations with optional filtering
    
    Args:
        work_package_id: Filter relations involving this work package ID (optional)
        relation_type: Filter by relation type (optional)
    """
    try:
        c = await get_client()
        import json
        filters = []
        if work_package_id:
            filters.append({"involved": {"operator": "=", "values": [str(work_package_id)]}})
        if relation_type:
            filters.append({"type": {"operator": "=", "values": [relation_type]}})
        
        filters_str = json.dumps(filters) if filters else None
        result = await c.list_work_package_relations(filters=filters_str)
        
        relations = result.get("_embedded", {}).get("elements", [])
        
        if not relations:
            return "No relations found."
        
        text = f"🔗 Work Package Relations ({len(relations)} found):\n\n"
        for r in relations:
            from_wp = r.get("_embedded", {}).get("from", {})
            to_wp = r.get("_embedded", {}).get("to", {})
            text += f"#{from_wp.get('id', 'N/A')} {r.get('type', 'N/A')} #{to_wp.get('id', 'N/A')}\n"
        
        return text
    except Exception as e:
        logger.error(f"Error listing relations: {e}", exc_info=True)
        return f"❌ Error: {str(e)}"


@mcp.tool()
async def update_work_package_relation(
    relation_id: int,
    relation_type: Optional[str] = None,
    lag: Optional[int] = None,
    description: Optional[str] = None
) -> str:
    """
    Update an existing work package relation
    
    Args:
        relation_id: The relation ID
        relation_type: New relation type (optional)
        lag: Lag in working days (optional)
        description: Optional description (optional)
    """
    try:
        c = await get_client()
        data = {}
        if relation_type is not None:
            data["relation_type"] = relation_type
        if lag is not None:
            data["lag"] = lag
        if description is not None:
            data["description"] = description
        
        await c.update_work_package_relation(relation_id, data)
        return f"✅ Relation #{relation_id} updated successfully"
    except Exception as e:
        logger.error(f"Error updating relation: {e}", exc_info=True)
        return f"❌ Error: {str(e)}"


@mcp.tool()
async def delete_work_package_relation(relation_id: int) -> str:
    """
    Delete a work package relation
    
    Args:
        relation_id: The relation ID
    """
    try:
        c = await get_client()
        await c.delete_work_package_relation(relation_id)
        return f"✅ Relation #{relation_id} deleted successfully"
    except Exception as e:
        logger.error(f"Error deleting relation: {e}", exc_info=True)
        return f"❌ Error: {str(e)}"


@mcp.tool()
async def get_work_package_relation(relation_id: int) -> str:
    """
    Get detailed information about a specific work package relation
    
    Args:
        relation_id: The relation ID
    """
    try:
        c = await get_client()
        r = await c.get_work_package_relation(relation_id)
        
        from_wp = r.get("_embedded", {}).get("from", {})
        to_wp = r.get("_embedded", {}).get("to", {})
        
        text = f"🔗 Relation #{r['id']}\n\n"
        text += f"- **Type**: {r.get('type', 'N/A')}\n"
        text += f"- **From**: #{from_wp.get('id', 'N/A')} - {from_wp.get('subject', 'N/A')}\n"
        text += f"- **To**: #{to_wp.get('id', 'N/A')} - {to_wp.get('subject', 'N/A')}\n"
        if r.get("lag"):
            text += f"- **Lag**: {r['lag']} days\n"
        
        return text
    except Exception as e:
        logger.error(f"Error getting relation: {e}", exc_info=True)
        return f"❌ Error: {str(e)}"


@mcp.tool()
async def check_permissions() -> str:
    """Check user permissions and capabilities"""
    try:
        c = await get_client()
        user = await c.check_permissions()
        
        text = f"👤 Current User: **{user.get('name', 'N/A')}**\n\n"
        text += f"- **ID**: {user['id']}\n"
        text += f"- **Login**: {user.get('login', 'N/A')}\n"
        text += f"- **Email**: {user.get('email', 'N/A')}\n"
        text += f"- **Admin**: {user.get('admin', False)}\n"
        
        return text
    except Exception as e:
        logger.error(f"Error checking permissions: {e}", exc_info=True)
        return f"❌ Error: {str(e)}"


# ============================================================================
# Server Initialization
# ============================================================================

async def main():
    """Main entry point"""
    logger.info(f"Starting OpenProject MCP Server v{__version__}")
    
    # Check transport mode
    use_http = os.getenv("USE_HTTP_TRANSPORT", "true").lower() == "true"
    
    if use_http:
        host = os.getenv("HTTP_HOST", "0.0.0.0")
        port = int(os.getenv("HTTP_PORT", "8008"))
        
        logger.info(f"🚀 Starting HTTP server on http://{host}:{port}")
        
        # Run FastMCP server with built-in HTTP support
        await mcp.run_http_async(host=host, port=port)
    else:
        # Run with stdio transport
        logger.info("🚀 Starting stdio transport")
        await mcp.run_stdio_async()


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
