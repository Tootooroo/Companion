"""Salesforce Case routes for MTV MAP Companion Reassign workflows.

The values here are the operator-provided routing table for the portable
Paperwork Companion.  A route describes only the fields the Companion should
set.  Fields omitted from a route are intentionally left alone.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


class SalesforceRouteError(ValueError):
    """Raised when the user has not supplied a valid Salesforce route choice."""


@dataclass(frozen=True)
class SalesforceCaseFields:
    operation: str
    case_type: str
    component: str
    resolution_reason: str = "Google Migrated"
    sub_category: str | None = None

    def as_dict(self) -> dict[str, str]:
        values = {
            "Operation": self.operation,
            "Type": self.case_type,
            "Component": self.component,
            "Resolution Reason": self.resolution_reason,
        }
        if self.sub_category:
            values["Sub Category"] = self.sub_category
        return values


# UI metadata. "when" means a selector is only required when another selector
# has the specified value.
_FORM_SPECS: dict[str, dict[str, Any]] = {
    "Mechatronics": {
        "selectors": [
            {
                "key": "route",
                "label": "Equipment",
                "options": ["MANUS", "OTHER"],
            },
        ],
    },
    "Lab Build Team": {
        "selectors": [
            {
                "key": "route",
                "label": "Route",
                "options": ["GANTRY", "SHARPA", "ESTOP"],
            },
            {
                "key": "operation",
                "label": "Operation",
                "options": [
                    "Data Collection / Teleoperation",
                    "Evaluation / Autonomous Behavior",
                ],
                "when": {"key": "route", "value": "SHARPA"},
            },
            {
                "key": "sub_category",
                "label": "Sub Category",
                "options": ["R Hand", "L Hand"],
                "when": {"key": "route", "value": "SHARPA"},
            },
        ],
    },
    "Release Team": {
        "selectors": [
            {
                "key": "operation",
                "label": "Operation",
                "options": ["Robot Positioning / Locomotion", "Robot Start-Up"],
            },
            {
                "key": "component",
                "label": "Component",
                "options": [
                    "Ansible",
                    "Apollo Operator",
                    "Robotics UI",
                    "SW Update",
                    "Configuration",
                    "Unknown Software",
                ],
            },
        ],
    },
    "Research Team": {
        "selectors": [
            {
                "key": "operation",
                "label": "Operation",
                "options": [
                    "Robot Positioning / Locomotion",
                    "Evaluation / Autonomous Behavior",
                ],
            },
            {
                "key": "component",
                "label": "Component",
                "options": [
                    "Apollo Operator",
                    "Helios",
                    "Robotics UI",
                    "Configuration",
                    "Orca",
                    "Tracking/IK",
                    "Unknown Software",
                ],
            },
        ],
    },
    "Engineering Team": {
        "selectors": [
            {
                "key": "operation",
                "label": "Operation",
                "options": [
                    "Robot Positioning / Locomotion",
                    "Evaluation / Autonomous Behavior",
                ],
            },
            {
                "key": "component",
                "label": "Component",
                "options": [
                    "Apollo Operator",
                    "Helios",
                    "Robotics UI",
                    "Orca",
                    "Configuration",
                    "Unknown Software",
                ],
            },
        ],
    },
    "Other": {
        "selectors": [],
    },
}


def get_reassign_form_spec(team: str) -> dict[str, Any]:
    """Return the safe UI selector specification for one Reassign team."""
    try:
        spec = _FORM_SPECS[team]
    except KeyError as error:
        raise SalesforceRouteError(
            f"No Salesforce route is configured for {team!r}."
        ) from error
    # Callers render this only; return a shallow-safe copy.
    return {
        "selectors": [
            {
                **selector,
                "options": list(selector.get("options", ())),
                **(
                    {"when": dict(selector["when"])}
                    if selector.get("when")
                    else {}
                ),
            }
            for selector in spec["selectors"]
        ]
    }


def _choice(
    selections: dict[str, str],
    key: str,
    allowed: tuple[str, ...] | list[str],
    label: str,
) -> str:
    value = str(selections.get(key, "") or "").strip()
    if value not in allowed:
        raise SalesforceRouteError(f"Choose a valid {label}.")
    return value


def resolve_reassign_route(
    team: str,
    selections: dict[str, str] | None,
) -> SalesforceCaseFields:
    """Resolve one team + user choices into exact Salesforce Case values."""
    selections = {
        str(key): str(value or "").strip()
        for key, value in (selections or {}).items()
    }

    if team == "Mechatronics":
        route = _choice(selections, "route", ["MANUS", "OTHER"], "Equipment")
        component = "Manus" if route == "MANUS" else "Misc. HARDWARE"
        return SalesforceCaseFields(
            operation="Data Collection / Teleoperation",
            case_type="Hardware",
            sub_category="Teleop Headset & Accessories",
            component=component,
        )

    if team == "Lab Build Team":
        route = _choice(
            selections,
            "route",
            ["GANTRY", "SHARPA", "ESTOP"],
            "Route",
        )
        if route == "GANTRY":
            return SalesforceCaseFields(
                operation="Robot Start-Up",
                case_type="Hardware",
                sub_category="Gantry",
                component="Full Assembly",
            )
        if route == "ESTOP":
            return SalesforceCaseFields(
                operation="Robot Positioning / Locomotion",
                case_type="Hardware",
                sub_category="E-Stop",
                component="E-Stop",
            )
        operation = _choice(
            selections,
            "operation",
            [
                "Data Collection / Teleoperation",
                "Evaluation / Autonomous Behavior",
            ],
            "Operation",
        )
        sub_category = _choice(
            selections,
            "sub_category",
            ["R Hand", "L Hand"],
            "Sub Category",
        )
        return SalesforceCaseFields(
            operation=operation,
            case_type="Hardware",
            sub_category=sub_category,
            component="Sharpa Cable",
        )

    if team == "Release Team":
        operation = _choice(
            selections,
            "operation",
            ["Robot Positioning / Locomotion", "Robot Start-Up"],
            "Operation",
        )
        component = _choice(
            selections,
            "component",
            [
                "Ansible",
                "Apollo Operator",
                "Robotics UI",
                "SW Update",
                "Configuration",
                "Unknown Software",
            ],
            "Component",
        )
        return SalesforceCaseFields(
            operation=operation,
            case_type="Software",
            component=component,
        )

    if team == "Research Team":
        operation = _choice(
            selections,
            "operation",
            [
                "Robot Positioning / Locomotion",
                "Evaluation / Autonomous Behavior",
            ],
            "Operation",
        )
        component = _choice(
            selections,
            "component",
            [
                "Apollo Operator",
                "Helios",
                "Robotics UI",
                "Configuration",
                "Orca",
                "Tracking/IK",
                "Unknown Software",
            ],
            "Component",
        )
        return SalesforceCaseFields(
            operation=operation,
            case_type="Software",
            component=component,
        )

    if team == "Engineering Team":
        operation = _choice(
            selections,
            "operation",
            [
                "Robot Positioning / Locomotion",
                "Evaluation / Autonomous Behavior",
            ],
            "Operation",
        )
        component = _choice(
            selections,
            "component",
            [
                "Apollo Operator",
                "Helios",
                "Robotics UI",
                "Orca",
                "Configuration",
                "Unknown Software",
            ],
            "Component",
        )
        return SalesforceCaseFields(
            operation=operation,
            case_type="Software",
            component=component,
        )

    if team == "Other":
        return SalesforceCaseFields(
            operation="Robot Start-Up",
            case_type="Software",
            component="Dev PC",
        )

    raise SalesforceRouteError(f"No Salesforce route is configured for {team!r}.")
