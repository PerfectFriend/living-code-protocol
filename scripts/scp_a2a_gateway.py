#!/usr/bin/env python3
"""
SCP ↔ A2A Gateway Adapter

SCP v0.18.8 (Internal Protocol) ↔ A2A Python SDK (Apache-2.0)
Гейт-адаптер: Contact → Agent Card, Handoff → Task, Handback → Artifacts
НЕ переписываем SCP — только адаптер.
"""

import json
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict, field
from enum import Enum
from pathlib import Path
import sys


class SCPMessageType(Enum):
    """Типы сообщений SCP протокола."""
    CONTACT = "contact"
    HANDOFF = "handoff"
    HANDBACK = "handback"
    HEARTBEAT = "heartbeat"
    ERROR = "error"


class A2AMessageType(Enum):
    """Типы сообщений A2A протокола."""
    AGENT_CARD = "agent_card"
    TASK = "task"
    TASK_STATUS_UPDATE = "task_status_update"
    TASK_ARTIFACT_UPDATE = "task_artifact_update"
    MESSAGE = "message"


@dataclass
class SCPContact:
    """SCP Contact — представление агента."""
    agent_id: str
    capabilities: List[str]
    protocol_version: str = "0.18.8"
    metadata: Dict = field(default_factory=dict)


@dataclass
class SCPPayload:
    """Базовый SCP payload."""
    message_id: str
    message_type: SCPMessageType
    sender_id: str
    recipient_id: Optional[str] = None
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"))
    payload: Dict = field(default_factory=dict)


@dataclass
class A2AAgentCard:
    """A2A Agent Card — описание возможностей агента."""
    name: str
    description: str
    url: str
    version: str
    capabilities: Dict = field(default_factory=dict)
    skills: List[Dict] = field(default_factory=list)
    default_input_modes: List[str] = field(default_factory=lambda: ["text"])
    default_output_modes: List[str] = field(default_factory=lambda: ["text"])
    metadata: Dict = field(default_factory=dict)


@dataclass
class A2ATask:
    """A2A Task — единица работы."""
    id: str
    status: str  # submitted, working, completed, failed, cancelled
    message: Optional[Dict] = None
    artifacts: List[Dict] = field(default_factory=list)
    metadata: Dict = field(default_factory=dict)


class SCPToA2AAdapter:
    """Адаптер SCP → A2A."""
    
    def __init__(self, base_url: str = "http://localhost:8080"):
        self.base_url = base_url
        self.agent_cards: Dict[str, A2AAgentCard] = {}
        self.tasks: Dict[str, A2ATask] = {}
    
    def contact_to_agent_card(self, contact: SCPContact) -> A2AAgentCard:
        """SCP Contact → A2A Agent Card."""
        agent_card = A2AAgentCard(
            name=f"SCP-Agent-{contact.agent_id}",
            description=f"SCP v{contact.protocol_version} agent with capabilities: {', '.join(contact.capabilities)}",
            url=f"{self.base_url}/agents/{contact.agent_id}",
            version=contact.protocol_version,
            capabilities={
                "streaming": True,
                "push_notifications": False,
                "state_transition_history": True,
            },
            skills=[
                {"id": cap, "name": cap, "description": f"SCP capability: {cap}"}
                for cap in contact.capabilities
            ],
            metadata=contact.metadata
        )
        self.agent_cards[contact.agent_id] = agent_card
        return agent_card
    
    def handoff_to_task(self, handoff_payload: Dict, sender_id: str, recipient_id: str) -> A2ATask:
        """SCP Handoff → A2A Task."""
        task_id = str(uuid.uuid4())
        task = A2ATask(
            id=task_id,
            status="submitted",
            message={
                "role": "user",
                "parts": [{"type": "text", "text": json.dumps(handoff_payload, ensure_ascii=False)}],
                "message_id": str(uuid.uuid4()),
                "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
            },
            metadata={
                "scp_sender": sender_id,
                "scp_recipient": recipient_id,
                "scp_handoff": True
            }
        )
        self.tasks[task_id] = task
        return task
    
    def handback_to_artifact(self, handback_payload: Dict, task_id: str) -> Dict:
        """SCP Handback → A2A Task Artifact Update."""
        if task_id not in self.tasks:
            raise ValueError(f"Task {task_id} not found")
        
        artifact = {
            "artifact_id": str(uuid.uuid4()),
            "name": "scp_handback_result",
            "description": "Result from SCP handback",
            "parts": [{
                "type": "data",
                "data": handback_payload
            }],
            "metadata": {
                "scp_handback": True,
                "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
            }
        }
        
        self.tasks[task_id].artifacts.append(artifact)
        self.tasks[task_id].status = "completed"
        return artifact


class A2AToSCPAdapter:
    """Адаптер A2A → SCP."""
    
    def __init__(self):
        self.pending_contacts: Dict[str, SCPContact] = {}
    
    def agent_card_to_contact(self, agent_card: A2AAgentCard) -> SCPContact:
        """A2A Agent Card → SCP Contact."""
        # Извлекаем capabilities из skills
        capabilities = [skill.get("id", skill.get("name", "")) for skill in agent_card.skills]
        
        contact = SCPContact(
            agent_id=agent_card.name.replace("SCP-Agent-", ""),
            capabilities=capabilities,
            protocol_version=agent_card.version,
            metadata={
                "a2a_url": agent_card.url,
                "a2a_description": agent_card.description,
                "a2a_capabilities": agent_card.capabilities
            }
        )
        self.pending_contacts[contact.agent_id] = contact
        return contact
    
    def task_to_handoff(self, task: A2ATask) -> Dict:
        """A2A Task → SCP Handoff payload."""
        # Извлекаем исходный payload из сообщения
        handoff_payload = {}
        if task.message and task.message.get("parts"):
            for part in task.message["parts"]:
                if part.get("type") == "text":
                    try:
                        handoff_payload = json.loads(part["text"])
                    except json.JSONDecodeError:
                        handoff_payload = {"raw_text": part["text"]}
        
        return {
            "task_id": task.id,
            "payload": handoff_payload,
            "metadata": task.metadata
        }
    
    def artifact_to_handback(self, artifact: Dict) -> Dict:
        """A2A Artifact → SCP Handback payload."""
        handback_payload = {}
        if artifact.get("parts"):
            for part in artifact["parts"]:
                if part.get("type") == "data":
                    handback_payload = part["data"]
                    break
        
        return {
            "artifact_id": artifact.get("artifact_id"),
            "payload": handback_payload,
            "metadata": artifact.get("metadata", {})
        }


class SCPA2AGateway:
    """Главный гейт-адаптер SCP ↔ A2A."""
    
    def __init__(self, base_url: str = "http://localhost:8080"):
        self.scp_to_a2a = SCPToA2AAdapter(base_url)
        self.a2a_to_scp = A2AToSCPAdapter()
        self.message_log: List[Dict] = []
    
    def handle_scp_message(self, scp_message: SCPPayload) -> Dict:
        """Обрабатывает входящее SCP сообщение и возвращает A2A эквивалент."""
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "direction": "SCP→A2A",
            "scp_type": scp_message.message_type.value,
            "sender": scp_message.sender_id,
            "recipient": scp_message.recipient_id
        }
        
        if scp_message.message_type == SCPMessageType.CONTACT:
            contact = SCPContact(**scp_message.payload)
            agent_card = self.scp_to_a2a.contact_to_agent_card(contact)
            log_entry["result"] = "agent_card_created"
            log_entry["agent_card_id"] = contact.agent_id
            self.message_log.append(log_entry)
            return {"type": "agent_card", "data": asdict(agent_card)}
        
        elif scp_message.message_type == SCPMessageType.HANDOFF:
            task = self.scp_to_a2a.handoff_to_task(
                scp_message.payload,
                scp_message.sender_id,
                scp_message.recipient_id or ""
            )
            log_entry["result"] = "task_created"
            log_entry["task_id"] = task.id
            self.message_log.append(log_entry)
            return {"type": "task", "data": asdict(task)}
        
        elif scp_message.message_type == SCPMessageType.HANDBACK:
            # Для handback нужен task_id в payload
            task_id = scp_message.payload.get("task_id")
            if not task_id:
                log_entry["error"] = "task_id required for handback"
                self.message_log.append(log_entry)
                return {"error": "task_id required for handback"}
            
            artifact = self.scp_to_a2a.handback_to_artifact(scp_message.payload, task_id)
            log_entry["result"] = "artifact_created"
            log_entry["artifact_id"] = artifact["artifact_id"]
            self.message_log.append(log_entry)
            return {"type": "artifact_update", "data": artifact}
        
        else:
            log_entry["result"] = "unsupported_type"
            self.message_log.append(log_entry)
            return {"error": f"Unsupported SCP message type: {scp_message.message_type.value}"}
    
    def handle_a2a_message(self, a2a_type: str, data: Dict) -> Dict:
        """Обрабатывает входящее A2A сообщение и возвращает SCP эквивалент."""
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "direction": "A2A→SCP",
            "a2a_type": a2a_type
        }
        
        if a2a_type == "agent_card":
            agent_card = A2AAgentCard(**data)
            contact = self.a2a_to_scp.agent_card_to_contact(agent_card)
            log_entry["result"] = "contact_created"
            log_entry["agent_id"] = contact.agent_id
            self.message_log.append(log_entry)
            return {"type": "contact", "data": asdict(contact)}
        
        elif a2a_type == "task":
            task = A2ATask(**data)
            handoff = self.a2a_to_scp.task_to_handoff(task)
            log_entry["result"] = "handoff_created"
            log_entry["task_id"] = task.id
            self.message_log.append(log_entry)
            return {"type": "handoff", "data": handoff}
        
        elif a2a_type == "artifact_update":
            handback = self.a2a_to_scp.artifact_to_handback(data)
            log_entry["result"] = "handback_created"
            log_entry["artifact_id"] = data.get("artifact_id")
            self.message_log.append(log_entry)
            return {"type": "handback", "data": handback}
        
        else:
            log_entry["result"] = "unsupported_type"
            self.message_log.append(log_entry)
            return {"error": f"Unsupported A2A message type: {a2a_type}"}
    
    def get_log(self) -> List[Dict]:
        """Возвращает лог сообщений."""
        return self.message_log
    
    def clear_log(self):
        """Очищает лог."""
        self.message_log.clear()


def demo():
    """Демонстрация работы адаптера."""
    gateway = SCPA2AGateway("http://localhost:8080")
    
    print("=== SCP → A2A ===")
    
    # 1. Contact → Agent Card
    contact = SCPContact(
        agent_id="coder-superguard",
        capabilities=["code_generation", "test_writing", "refactoring", "debugging"],
        metadata={"model": "mistralai/mistral-large-4-1t-a52b", "provider": "nvidia"}
    )
    result = gateway.handle_scp_message(SCPPayload(
        message_id=str(uuid.uuid4()),
        message_type=SCPMessageType.CONTACT,
        sender_id="orchestrator",
        recipient_id="coder-superguard",
        payload=asdict(contact)
    ))
    print(f"Contact → Agent Card: {result['type']}")
    print(f"  Agent: {result['data']['name']}")
    print(f"  Skills: {[s['id'] for s in result['data']['skills']]}")
    
    # 2. Handoff → Task
    handoff_payload = {
        "task": "Fix Evidence Gate failures",
        "context": "Multiple agents failing with HOLLOW_DETECTED and GROUNDED_NUMBERS_FAILED",
        "files": ["evidence_gate.py", "living_code_agent_wrapper.py"]
    }
    result = gateway.handle_scp_message(SCPPayload(
        message_id=str(uuid.uuid4()),
        message_type=SCPMessageType.HANDOFF,
        sender_id="inquisitor",
        recipient_id="coder-superguard",
        payload=handoff_payload
    ))
    print(f"\nHandoff → Task: {result['type']}")
    print(f"  Task ID: {result['data']['id']}")
    print(f"  Status: {result['data']['status']}")
    task_id = result['data']['id']
    
    # 3. Handback → Artifact
    handback_payload = {
        "task_id": task_id,
        "result": "Fixed Evidence Gate - added conftest.py for pytest path",
        "files_changed": ["Project2/tests/conftest.py"],
        "tests_passing": True
    }
    result = gateway.handle_scp_message(SCPPayload(
        message_id=str(uuid.uuid4()),
        message_type=SCPMessageType.HANDBACK,
        sender_id="coder-superguard",
        recipient_id="inquisitor",
        payload=handback_payload
    ))
    print(f"\nHandback → Artifact: {result['type']}")
    print(f"  Artifact ID: {result['data']['artifact_id']}")
    print(f"  Task Status: completed")
    
    print("\n=== A2A → SCP ===")
    
    # 4. Agent Card → Contact
    agent_card = A2AAgentCard(
        name="SCP-Agent-auditor",
        description="Auditor agent for Living Code Protocol",
        url="http://localhost:8080/agents/auditor",
        version="0.18.8",
        skills=[
            {"id": "audit", "name": "audit", "description": "Code audit"},
            {"id": "review", "name": "review", "description": "Code review"}
        ]
    )
    result = gateway.handle_a2a_message("agent_card", asdict(agent_card))
    print(f"Agent Card → Contact: {result['type']}")
    print(f"  Agent ID: {result['data']['agent_id']}")
    print(f"  Capabilities: {result['data']['capabilities']}")
    
    print("\n=== Message Log ===")
    for entry in gateway.get_log():
        print(f"  {entry['timestamp']} | {entry['direction']} | {entry.get('scp_type', entry.get('a2a_type', 'N/A'))} → {entry['result']}")


if __name__ == "__main__":
    demo()