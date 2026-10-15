"""Minimal honest empty feast repo: one entity, zero feature views.

Matches chart global.project=default, provider local. `feast apply` on this
directory produces a REAL protobuf registry.db (no fake content).
"""

from feast import Entity

customer = Entity(name="customer", join_keys=["customer_id"])
