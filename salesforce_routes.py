"""Salesforce Case routes for MTV MAP Companion Reassign and Claim workflows.

The values here are the operator-provided routing tables for the portable
Paperwork Companion. A route describes only the fields the Companion should
set. Fields omitted from a route are intentionally left alone.
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


def _choice(
    selections: dict[str, str],
    key: str,
    allowed: tuple[str, ...] | list[str],
    label: str,
) -> str:
    """Helper to validate that a given selection is explicitly allowed."""
    value = str(selections.get(key, "") or "").strip()
    if value not in allowed:
        raise SalesforceRouteError(f"Choose a valid {label}.")
    return value


# ==========================================
# 1. REASSIGN WORKFLOW
# ==========================================

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


# ==========================================
# 2. CLAIM WORKFLOW
# ==========================================

_CLAIM_OPERATIONS = [
    "Robot Start-Up",
    "Robot Positioning / Locomotion",
    "Data Collection / Teleoperation",
    "Evaluation / Autonomous Behavior",
    "Robot Power-Down",
    "Repair",
]

# Hardware map: Sub Category -> {Component: Resolution Reason}
_CLAIM_HARDWARE = {
    "Head": {
        "Covers": "Resolved",
        "Cranium": "Hardware replaced",
    },
    "Neck": {
        "ACT - PB70 - Neck/Wrist L1 + L2": "Hardware replaced",
        "Neck Harness": "Hardware replaced",
        "Neck Mount": "Resolved",
        "Splitter Harness": "Hardware replaced",
    },
    "Torso": {
        "ACT - PB250-05 - Elbow_L1 FE (SISO)": "Hardware replaced",
        "ACT - PB320-03 - Torso_L1 + L2": "Hardware replaced",
        "Covers": "Resolved",
        "GSML": "Hardware replaced",
        "Splitter - 5way": "Hardware replaced",
        "RCM": "Hardware replaced",
        "Splitter Harness": "Hardware replaced",
        "Torso to Pelvis Harness": "Hardware replaced",
    },
    "R Arm": {
        "ACT - PB250-05 - Elbow_L1 FE (SISO)": "Hardware replaced",
        "ACT - PB70 - Neck/Wrist L1 + L2": "Hardware replaced",
        "Covers": "Resolved",
        "GSML": "Hardware replaced",
        "Splitter - 5way": "Hardware replaced",
        "Splitter Harness": "Hardware replaced",
        "Splitter - 3way": "Hardware replaced",
        "Wrist Mount": "Hardware replaced",
    },
    "L Arm": {
        "ACT - PB250-05 - Elbow_L1 FE (SISO)": "Hardware replaced",
        "ACT - PB70 - Neck/Wrist L1 + L2": "Hardware replaced",
        "Covers": "Resolved",
        "GSML": "Hardware replaced",
        "Splitter - 5way": "Hardware replaced",
        "Splitter Harness": "Hardware replaced",
        "Splitter - 3way": "Hardware replaced",
        "Wrist Mount": "Hardware replaced",
    },
    "R Hand": {
        "Inspire Hand": "Hardware replaced",
        "Sharpa Cable": "Hardware replaced",
        "Sharpa Hand": "Hardware replaced",
        "Sharpa Skin": "Resolved",
    },
    "L Hand": {
        "Inspire Hand": "Hardware replaced",
        "Sharpa Cable": "Hardware replaced",
        "Sharpa Hand": "Hardware replaced",
        "Sharpa Skin": "Resolved",
    },
    "R Leg": {
        "ACT - PB1000-02 - Knee_L1 FE": "Hardware replaced",
        "ACT - PB250-06 - Ankle_L1 + L2 FE/IE (MIMO)": "Hardware replaced",
        "ACT - PB550-02 - Hip_L1 + L2 FE/AA": "Hardware replaced",
        "Covers": "Resolved",
        "Fans": "Hardware replaced",
        "Kneepads": "Resolved",
        "Splitter - 5way": "Hardware replaced",
        "Splitter Harness": "Hardware replaced",
    },
    "L Leg": {
        "ACT - PB1000-02 - Knee_L1 FE": "Hardware replaced",
        "ACT - PB250-06 - Ankle_L1 + L2 FE/IE (MIMO)": "Hardware replaced",
        "ACT - PB550-02 - Hip_L1 + L2 FE/AA": "Hardware replaced",
        "Covers": "Resolved",
        "Fans": "Hardware replaced",
        "Kneepads": "Resolved",
        "Splitter - 5way": "Hardware replaced",
        "Splitter Harness": "Hardware replaced",
    },
    "R Ankle/Foot": {
        "ACT - PB250-06 - Ankle_L1 + L2 FE/IE (MIMO)": "Hardware replaced",
    },
    "L Ankle/Foot": {
        "ACT - PB250-06 - Ankle_L1 + L2 FE/IE (MIMO)": "Hardware replaced",
    },
    "Actuator Fault": {
        "ACT - PB1000-02 - Knee_L1 FE": "Hardware replaced",
        "ACT - PB250-05 - Elbow_L1 FE (SISO)": "Hardware replaced",
        "ACT - PB250-06 - Ankle_L1 + L2 FE/IE (MIMO)": "Hardware replaced",
        "ACT - PB320-03 - Torso_L1 + L2": "Hardware replaced",
        "ACT - PB550-02 - Hip_L1 + L2 FE/AA": "Hardware replaced",
        "ACT - PB70 - Neck/Wrist L1 + L2": "Hardware replaced",
    },
    "Battery": {
        "Unknown Hardware": "Resolved",
    },
    "Teleop Headset & Accessories": {
        "Manus": "Resolved",
        "Misc. HARDWARE": "Resolved",
        "Misc. Harness": "Resolved",
        "Power Cable": "Resolved",
        "Unknown Hardware": "Resolved",
    },
    "Thermal Fault": {
        "ACT - PB1000-02 - Knee_L1 FE": "Resolved",
        "ACT - PB250-05 - Elbow_L1 FE (SISO)": "Resolved",
        "ACT - PB250-06 - Ankle_L1 + L2 FE/IE (MIMO)": "Resolved",
        "ACT - PB320-03 - Torso_L1 + L2": "Resolved",
        "ACT - PB550-02 - Hip_L1 + L2 FE/AA": "Resolved",
        "ACT - PB70 - Neck/Wrist L1 + L2": "Resolved",
        "ACT - RB150-01": "Resolved",
        "ACT - RB430-02": "Resolved",
    },
}

# Non-Hardware map: Type -> {Component (Sub Category): Resolution Reason}
_CLAIM_NON_HARDWARE = {
    "Software": {
        "Ansible": "Resolved",
        "Apollo Operator": "Resolved",
        "Configuration": "Resolved",
        "Dev PC": "Resolved",
        "Ecat Watchdog": "Resolved",
        "Firmware": "Resolved",
        "GS Frame Drop": "Resolved",
        "GS Velocity": "Resolved",
        "Helios": "Resolved",
        "Isaac Agent / Disk Space": "Resolved",
        "Locomotion Failure": "Resolved",
        "Operator Error": "Resolved",
        "Shem": "Resolved",
        "Wrist Cameras": "Recalibration",
    },
    "Collision": {
        "Falls": "Resolved",
    },
    "Falsely Identified Issue": {
        "Operator Error": "Resolved",
    },
    "Field Service Request": {
        "Investigation": "Resolved",
    },
    "IT": {
        "Network": "Resolved",
    },
    "Operations": {
        "Data Request": "Resolved",
    },
}

# Build a two-choice Claim workflow:
#   1. what the robot was doing -> Operation
#   2. what the issue was       -> Type/Sub Category/Component/Resolution Reason
#
# The raw routing tables above remain the source of truth.  We flatten them into
# a single Issue selector while preserving enough context to disambiguate
# repeated component names such as Covers, Operator Error, or actuator names.


def _claim_issue_records() -> list[dict[str, str]]:
    """Return every valid Claim issue as an exact Salesforce route fragment."""
    records: list[dict[str, str]] = []

    for sub_category, components in _CLAIM_HARDWARE.items():
        for component, resolution_reason in components.items():
            records.append(
                {
                    "case_type": "Hardware",
                    "sub_category": sub_category,
                    "component": component,
                    "resolution_reason": resolution_reason,
                }
            )

    for case_type, components in _CLAIM_NON_HARDWARE.items():
        for component, resolution_reason in components.items():
            records.append(
                {
                    "case_type": case_type,
                    "sub_category": "",
                    "component": component,
                    "resolution_reason": resolution_reason,
                }
            )

    return records


def _claim_issue_options() -> list[str]:
    """Return concise, unique labels for the single Claim Issue selector.

    A component that is unique across the whole Claim taxonomy is displayed by
    itself (for example ``Ansible``).  Repeated component names receive only the
    minimum context needed to distinguish them.
    """
    records = _claim_issue_records()

    counts: dict[str, int] = {}
    for record in records:
        component = record["component"]
        counts[component] = counts.get(component, 0) + 1

    options: list[str] = []
    for record in records:
        component = record["component"]
        if counts[component] == 1:
            label = component
        elif record["case_type"] == "Hardware":
            label = f"{component} — {record['sub_category']}"
        else:
            label = f"{component} — {record['case_type']}"
        options.append(label)

    return sorted(options, key=str.casefold)


def _claim_issue_lookup() -> dict[str, dict[str, str]]:
    """Map each rendered Issue label back to exact Salesforce field values."""
    records = _claim_issue_records()

    counts: dict[str, int] = {}
    for record in records:
        component = record["component"]
        counts[component] = counts.get(component, 0) + 1

    lookup: dict[str, dict[str, str]] = {}
    for record in records:
        component = record["component"]
        if counts[component] == 1:
            label = component
        elif record["case_type"] == "Hardware":
            label = f"{component} — {record['sub_category']}"
        else:
            label = f"{component} — {record['case_type']}"

        if label in lookup:
            raise RuntimeError(f"Duplicate Claim issue label: {label}")
        lookup[label] = dict(record)

    return lookup


_CLAIM_FORM_SPEC: dict[str, Any] = {
    "selectors": [
        {
            "key": "operation",
            "label": "Robot activity",
            "options": _CLAIM_OPERATIONS,
        },
        {
            "key": "issue",
            "label": "Issue",
            "options": _claim_issue_options(),
        },
    ]
}


def get_claim_form_spec() -> dict[str, Any]:
    """Return the minimal two-choice Claim UI specification."""
    return {
        "selectors": [
            {
                **selector,
                "options": list(selector.get("options", ())),
            }
            for selector in _CLAIM_FORM_SPEC["selectors"]
        ]
    }


def resolve_claim_route(
    selections: dict[str, str] | None,
) -> SalesforceCaseFields:
    """Resolve Robot activity + Issue into the complete Salesforce Case route."""
    selections = {
        str(key): str(value or "").strip()
        for key, value in (selections or {}).items()
    }

    operation = _choice(
        selections,
        "operation",
        _CLAIM_OPERATIONS,
        "Robot activity",
    )

    issue_lookup = _claim_issue_lookup()
    issue = _choice(
        selections,
        "issue",
        list(issue_lookup.keys()),
        "Issue",
    )
    route = issue_lookup[issue]

    return SalesforceCaseFields(
        operation=operation,
        case_type=route["case_type"],
        sub_category=route["sub_category"] or None,
        component=route["component"],
        resolution_reason=route["resolution_reason"],
    )

