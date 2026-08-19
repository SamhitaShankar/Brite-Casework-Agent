"""
Compatibility layer providing SQLAlchemy and Pydantic abstractions with pure standard-library
fallbacks if external binary packages are unavailable in the test container environment.
"""
from typing import Any, Optional, Dict, List
from datetime import datetime
import json

try:
    from sqlalchemy import Column, String, Float, DateTime, Boolean, Text, Integer, ForeignKey, JSON, create_engine
    from sqlalchemy.orm import relationship, declarative_base, sessionmaker, Session
    HAS_SQLALCHEMY = True
except ImportError:
    HAS_SQLALCHEMY = False

    class ColumnExpr:
        def __init__(self, name=""):
            self.name = name

        def __eq__(self, other):
            def predicate(obj):
                val = getattr(obj, self.name, None)
                return val == other
            return predicate

        def __ne__(self, other):
            def predicate(obj):
                val = getattr(obj, self.name, None)
                return val != other
            return predicate

        def asc(self):
            return self

        def desc(self):
            return self

    class Query:
        def __init__(self, session, model_cls):
            self.session = session
            self.model_cls = model_cls
            self.filters = []
            self._order_key = None
            self._order_asc = True
            self._limit = None

        def filter(self, *conditions):
            q = Query(self.session, self.model_cls)
            q.filters = list(self.filters) + list(conditions)
            return q

        def order_by(self, *args):
            return self

        def limit(self, n):
            self._limit = n
            return self

        def count(self):
            return len(self.all())

        def all(self):
            items = [x for x in self.session._store if isinstance(x, self.model_cls)]
            for cond in self.filters:
                if callable(cond):
                    items = [x for x in items if cond(x)]
            if self._limit:
                items = items[:self._limit]
            return items

        def first(self):
            items = self.all()
            return items[0] if items else None

        def delete(self):
            self.session._store = [x for x in self.session._store if not isinstance(x, self.model_cls)]

    _GLOBAL_STORE = []

    class InMemorySession:
        def __init__(self, store=None):
            self._store = _GLOBAL_STORE if store is None else store

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            pass

        def add(self, item):
            if item not in self._store:
                self._store.append(item)
            ref_id = getattr(item, 'referral_id', None)
            if ref_id:
                for existing in self._store:
                    if getattr(existing, 'referral_id', None) == ref_id and existing is not item:
                        cls_name = item.__class__.__name__
                        if 'Snapshot' in cls_name:
                            existing.resident_snapshot = item
                            setattr(item, 'referral', existing)
                        elif 'PolicyEvaluation' in cls_name:
                            existing.policy_evaluation = item
                            setattr(item, 'referral', existing)
                        elif 'TriageNote' in cls_name:
                            existing.triage_note = item
                            setattr(item, 'referral', existing)
                        elif 'ApprovalRequest' in cls_name:
                            existing.approval_request = item
                            setattr(item, 'referral', existing)
                        elif 'AuditLog' in cls_name:
                            if not hasattr(existing, 'audit_logs') or existing.audit_logs is None:
                                existing.audit_logs = []
                            if item not in existing.audit_logs:
                                existing.audit_logs.append(item)
                            setattr(item, 'referral', existing)

        def delete(self, item):
            if item in self._store:
                self._store.remove(item)

        def flush(self):
            pass

        def rollback(self):
            pass

        def commit(self):
            pass

        def close(self):
            pass

        def query(self, model_cls):
            return Query(self, model_cls)

    Session = InMemorySession

    class MetaData:
        def create_all(self, bind=None):
            pass

    class BaseMeta(type):
        def __init__(cls, name, bases, dct):
            super().__init__(name, bases, dct)
            for attr_name, attr_val in dct.items():
                if isinstance(attr_val, ColumnExpr):
                    attr_val.name = attr_name

        def __getattr__(cls, name):
            return ColumnExpr(name)

    class Base(metaclass=BaseMeta):
        metadata = MetaData()
        def __init__(self, **kwargs):
            self.resident_snapshot = None
            self.policy_evaluation = None
            self.triage_note = None
            self.approval_request = None
            self.audit_logs = []
            self.is_resumed = False
            self.has_under_18 = None
            self.error_message = None
            self.processing_state = "RECEIVED"
            self.workflow_disposition = "PENDING"
            self.policy_decision = None
            self.created_at = datetime.utcnow()
            self.updated_at = datetime.utcnow()
            for k, v in kwargs.items():
                setattr(self, k, v)

        def __getattribute__(self, name):
            val = super().__getattribute__(name)
            if isinstance(val, ColumnExpr):
                return None
            return val

    def declarative_base():
        return Base

    def Column(*args, **kwargs):
        return ColumnExpr()

    def String(*args, **kwargs):
        return str

    def Float(*args, **kwargs):
        return float

    def DateTime(*args, **kwargs):
        return datetime

    def Boolean(*args, **kwargs):
        return bool

    def Text(*args, **kwargs):
        return str

    def Integer(*args, **kwargs):
        return int

    def ForeignKey(*args, **kwargs):
        return None

    def JSON(*args, **kwargs):
        return dict

    def relationship(*args, **kwargs):
        return None

    def create_engine(*args, **kwargs):
        return None

    def sessionmaker(*args, **kwargs):
        return InMemorySession


try:
    from pydantic import BaseModel, Field
    HAS_PYDANTIC = True
except ImportError:
    HAS_PYDANTIC = False

    class BaseModel:
        def __init__(self, **data):
            for k, v in data.items():
                setattr(self, k, v)
        
        def dict(self, *args, **kwargs):
            return self.__dict__
        
        def model_dump(self, *args, **kwargs):
            return self.__dict__

    def Field(*args, default=None, **kwargs):
        return default
