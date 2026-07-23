"""Strict data models for deterministic LineageGuard decisions."""

from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ChangeKind(str, Enum):
    ADD_COLUMN = "add_column"
    DROP_COLUMN = "drop_column"
    RENAME_COLUMN = "rename_column"
    TYPE_CHANGE = "type_change"


class Verdict(str, Enum):
    ALLOW = "allow"
    REVIEW = "review"
    BLOCK = "block"


class Severity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class TargetSelector(StrictModel):
    query: str = Field(min_length=1)
    platform: str = Field(min_length=1, pattern=r"^[a-zA-Z0-9_-]+$")
    name: str = Field(min_length=1)
    env: str = Field(default="PROD", pattern=r"^[A-Z][A-Z0-9_-]*$")
    relation: str = Field(
        min_length=1,
        pattern=r"^[A-Za-z_][A-Za-z0-9_$]*(\.[A-Za-z_][A-Za-z0-9_$]*){0,2}$",
    )


class SchemaChange(StrictModel):
    scenario_id: str = Field(min_length=1, pattern=r"^[a-z0-9][a-z0-9_-]*$")
    target: TargetSelector
    kind: ChangeKind
    field_path: str = Field(min_length=1, pattern=r"^[A-Za-z_][A-Za-z0-9_.$]*$")
    before_type: str | None = None
    after_type: str | None = None
    new_field_path: str | None = Field(
        default=None, pattern=r"^[A-Za-z_][A-Za-z0-9_.$]*$"
    )

    @model_validator(mode="after")
    def validate_change_shape(self) -> "SchemaChange":
        if self.kind == ChangeKind.ADD_COLUMN and not self.after_type:
            raise ValueError("add_column requires after_type")
        if self.kind == ChangeKind.DROP_COLUMN and not self.before_type:
            raise ValueError("drop_column requires before_type")
        if self.kind == ChangeKind.TYPE_CHANGE and (
            not self.before_type or not self.after_type
        ):
            raise ValueError("type_change requires before_type and after_type")
        if self.kind == ChangeKind.RENAME_COLUMN and not self.new_field_path:
            raise ValueError("rename_column requires new_field_path")
        if (
            self.kind == ChangeKind.RENAME_COLUMN
            and self.new_field_path
            and self.new_field_path.casefold() == self.field_path.casefold()
        ):
            raise ValueError("rename_column requires a different new_field_path")
        if (
            self.kind == ChangeKind.TYPE_CHANGE
            and self.before_type
            and self.after_type
            and self.before_type.casefold() == self.after_type.casefold()
        ):
            raise ValueError("type_change requires different before_type and after_type")
        return self


class SchemaFieldEvidence(StrictModel):
    field_path: str
    native_type: str | None = None
    description: str | None = None
    tag_names: list[str] = Field(default_factory=list)
    term_names: list[str] = Field(default_factory=list)


class AssetImpact(StrictModel):
    urn: str = Field(pattern=r"^urn:li:")
    entity_type: str
    name: str
    platform: str | None = None
    degree: int = Field(ge=0)
    owner_urns: list[str] = Field(default_factory=list)
    domain_urns: list[str] = Field(default_factory=list)
    tag_urns: list[str] = Field(default_factory=list)
    term_urns: list[str] = Field(default_factory=list)
    impacted_columns: list[str] = Field(default_factory=list)


class ImpactSnapshot(StrictModel):
    source: AssetImpact
    field: SchemaFieldEvidence | None
    downstream_total: int = Field(ge=0)
    downstream: list[AssetImpact]
    lineage_complete: bool
    warnings: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_snapshot_shape(self) -> "ImpactSnapshot":
        if self.source.degree != 0:
            raise ValueError("source degree must be zero")
        if any(asset.degree < 1 for asset in self.downstream):
            raise ValueError("downstream asset degrees must be at least one")
        if len({asset.urn for asset in self.downstream}) != len(self.downstream):
            raise ValueError("downstream assets must be unique by URN")
        if self.downstream_total < len(self.downstream):
            raise ValueError("downstream_total cannot be smaller than retrieved assets")
        if self.lineage_complete and self.downstream_total != len(self.downstream):
            raise ValueError("complete lineage must contain every reported downstream asset")
        return self


class DecisionEvidence(StrictModel):
    source_field_verified: bool
    downstream_total: int = Field(ge=0)
    evaluated_downstream: int = Field(ge=0)
    direct_downstream: int = Field(ge=0)
    transitive_downstream: int = Field(ge=0)
    lineage_complete: bool


class OwnerRoute(StrictModel):
    owner_urn: str = Field(pattern=r"^urn:li:")
    asset_urns: list[str]


class ActionItem(StrictModel):
    action_id: str
    kind: Literal[
        "hold_deployment",
        "migrate_dependents",
        "notify_owners",
        "resolve_ownership",
        "run_validation",
    ]
    description: str
    asset_urns: list[str] = Field(default_factory=list)
    owner_urns: list[str] = Field(default_factory=list)


class ValidationQuery(StrictModel):
    query_id: str
    purpose: str
    sql: str


class DecisionArtifact(StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    decision_id: str
    scenario_id: str
    verdict: Verdict
    severity: Severity
    summary: str
    source: AssetImpact
    source_field: SchemaFieldEvidence | None
    field_path: str
    change_kind: ChangeKind
    evidence: DecisionEvidence
    impacted_assets: list[AssetImpact]
    owner_routes: list[OwnerRoute]
    reason_codes: list[str]
    required_actions: list[ActionItem]
    validation_queries: list[ValidationQuery]
    warnings: list[str] = Field(default_factory=list)
