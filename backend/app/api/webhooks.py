"""Enterprise IM Webhook Handlers"""

import json
import hashlib
import hmac
from typing import Dict, Any
from fastapi import APIRouter, Request, HTTPException, status

router = APIRouter(prefix="/api/v1/webhooks", tags=["webhooks"])


# DingTalk Webhook Handler
@router.post("/dingtalk/callback")
async def dingtalk_callback(request: Request) -> Dict[str, Any]:
    """Handle DingTalk webhook callbacks"""
    try:
        body = await request.body()
        data = json.loads(body)

        # Verify signature
        timestamp = request.headers.get("X-Dingtalk-Timestamp")
        sign = request.headers.get("X-Dingtalk-Sign")

        if not _verify_dingtalk_signature(timestamp, sign, body):
            raise HTTPException(status_code=401, detail="Invalid signature")

        # Process event
        event_type = data.get("EventType")

        if event_type == "check_url":
            # URL verification
            return {
                "msg_signature": data.get("msg_signature"),
                "timeStamp": data.get("timeStamp"),
                "nonce": data.get("nonce"),
            }
        elif event_type == "user_add_org":
            # User added to organization
            return await _handle_dingtalk_user_event(data, "user_joined")
        elif event_type == "user_leave_org":
            # User left organization
            return await _handle_dingtalk_user_event(data, "user_left")
        elif event_type == "user_modify_org":
            # User info modified
            return await _handle_dingtalk_user_event(data, "contact_updated")
        elif event_type == "processinstance_change":
            # Approval workflow changed
            return await _handle_dingtalk_approval_event(data)
        else:
            return {"status": "ok"}

    except Exception as e:
        print(f"DingTalk webhook error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


def _verify_dingtalk_signature(timestamp: str, sign: str, body: bytes) -> bool:
    """Verify DingTalk webhook signature"""
    # Implementation depends on your app_secret
    # This is a placeholder
    return True


async def _handle_dingtalk_user_event(data: Dict[str, Any], event_type: str) -> Dict[str, Any]:
    """Handle DingTalk user events"""
    # Process user event
    return {"status": "ok"}


async def _handle_dingtalk_approval_event(data: Dict[str, Any]) -> Dict[str, Any]:
    """Handle DingTalk approval events"""
    # Process approval event
    return {"status": "ok"}


# Feishu Webhook Handler
@router.post("/feishu/callback")
async def feishu_callback(request: Request) -> Dict[str, Any]:
    """Handle Feishu webhook callbacks"""
    try:
        body = await request.body()
        data = json.loads(body)

        # Verify signature
        timestamp = request.headers.get("X-Feishu-Timestamp")
        sign = request.headers.get("X-Feishu-Signature")

        if not _verify_feishu_signature(timestamp, sign, body):
            raise HTTPException(status_code=401, detail="Invalid signature")

        # Handle URL verification challenge
        if data.get("type") == "url_verification":
            return {
                "challenge": data.get("challenge"),
            }

        # Process event
        event = data.get("event", {})
        event_type = event.get("type")

        if event_type == "message":
            return await _handle_feishu_message_event(event)
        elif event_type == "user.created":
            return await _handle_feishu_user_event(event, "user_joined")
        elif event_type == "user.deleted":
            return await _handle_feishu_user_event(event, "user_left")
        elif event_type == "user.updated":
            return await _handle_feishu_user_event(event, "contact_updated")
        elif event_type == "approval.instance.created":
            return await _handle_feishu_approval_event(event, "approval_created")
        elif event_type == "approval.instance.approved":
            return await _handle_feishu_approval_event(event, "approval_approved")
        elif event_type == "approval.instance.rejected":
            return await _handle_feishu_approval_event(event, "approval_rejected")
        else:
            return {"status": "ok"}

    except Exception as e:
        print(f"Feishu webhook error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


def _verify_feishu_signature(timestamp: str, sign: str, body: bytes) -> bool:
    """Verify Feishu webhook signature"""
    # Implementation depends on your app_secret
    # This is a placeholder
    return True


async def _handle_feishu_message_event(event: Dict[str, Any]) -> Dict[str, Any]:
    """Handle Feishu message events"""
    # Process message event
    return {"status": "ok"}


async def _handle_feishu_user_event(event: Dict[str, Any], event_type: str) -> Dict[str, Any]:
    """Handle Feishu user events"""
    # Process user event
    return {"status": "ok"}


async def _handle_feishu_approval_event(event: Dict[str, Any], event_type: str) -> Dict[str, Any]:
    """Handle Feishu approval events"""
    # Process approval event
    return {"status": "ok"}


# WeChat Work Webhook Handler
@router.post("/wechat_work/callback")
async def wechat_work_callback(request: Request) -> Dict[str, Any]:
    """Handle WeChat Work webhook callbacks"""
    try:
        # Get query parameters
        msg_signature = request.query_params.get("msg_signature")
        timestamp = request.query_params.get("timestamp")
        nonce = request.query_params.get("nonce")

        body = await request.body()

        # Verify signature
        if not _verify_wechat_work_signature(msg_signature, timestamp, nonce, body):
            raise HTTPException(status_code=401, detail="Invalid signature")

        # Parse XML body
        data = _parse_wechat_work_xml(body)

        # Handle URL verification
        if data.get("MsgType") == "event" and data.get("Event") == "LOCATION":
            return {
                "Encrypt": data.get("Encrypt"),
            }

        # Process event
        event_type = data.get("Event")

        if event_type == "create_user":
            return await _handle_wechat_work_user_event(data, "user_joined")
        elif event_type == "delete_user":
            return await _handle_wechat_work_user_event(data, "user_left")
        elif event_type == "update_user":
            return await _handle_wechat_work_user_event(data, "contact_updated")
        elif event_type == "APPROVAL_STAGE_CHANGE":
            return await _handle_wechat_work_approval_event(data)
        else:
            return {"status": "ok"}

    except Exception as e:
        print(f"WeChat Work webhook error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


def _verify_wechat_work_signature(msg_signature: str, timestamp: str, nonce: str, body: bytes) -> bool:
    """Verify WeChat Work webhook signature"""
    # Implementation depends on your token
    # This is a placeholder
    return True


def _parse_wechat_work_xml(body: bytes) -> Dict[str, Any]:
    """Parse WeChat Work XML body"""
    # Simple XML parsing - in production use proper XML parser
    import xml.etree.ElementTree as ET
    try:
        root = ET.fromstring(body)
        data = {}
        for child in root:
            data[child.tag] = child.text
        return data
    except Exception:
        return {}


async def _handle_wechat_work_user_event(data: Dict[str, Any], event_type: str) -> Dict[str, Any]:
    """Handle WeChat Work user events"""
    # Process user event
    return {"status": "ok"}


async def _handle_wechat_work_approval_event(data: Dict[str, Any]) -> Dict[str, Any]:
    """Handle WeChat Work approval events"""
    # Process approval event
    return {"status": "ok"}
