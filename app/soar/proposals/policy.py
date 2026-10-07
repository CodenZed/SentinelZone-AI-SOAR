import ipaddress
import re

import yaml

from app.repositories.base import canonical
from app.errors import ServiceError


def role_name(value):
    return value.lower().strip().replace("-", "_").replace(" ", "_")


class TargetPolicy:
    def __init__(self, settings):
        data = yaml.safe_load(settings.policy_file.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or set(data) != {"protected_assets", "protected_roles", "protected_networks"}:
            raise ValueError("invalid policy file")
        if any(not isinstance(v, list) or any(not isinstance(x, str) for x in v) for v in data.values()):
            raise ValueError("policy lists must contain strings")
        self.names = {
            canonical(x) for x in data["protected_assets"] + settings.protected_assets.split(",") if x.strip()
        }
        self.lab_assets = {canonical(x) for x in settings.lab_asset_ids.split(",") if x.strip()}
        self.roles = {role_name(x) for x in data["protected_roles"]}
        self.networks = [
            ipaddress.ip_network(x.strip())
            for x in data["protected_networks"] + settings.protected_networks.split(",")
            if x.strip()
        ]

    def protected(self, target):
        target = canonical(target)
        if target in self.names or role_name(target) in self.roles:
            return True
        try:
            address = ipaddress.ip_address(target)
            if address.is_loopback or address.is_unspecified or address.is_multicast or address.is_link_local:
                return True
            if getattr(address, "ipv4_mapped", None):
                address = address.ipv4_mapped
            return any(address in network for network in self.networks)
        except ValueError:
            return False

    async def validate(self, target, action_type, parameters, tenant_id, core):
        original_target = target
        target = canonical(target)
        if self.protected(target):
            raise ServiceError("DENIED_PROTECTED_TARGET", 403)
        asset = await core.get_asset(target, tenant_id)
        if asset and (
            role_name(asset.role or "") in self.roles
            or asset.criticality.lower() == "critical"
            or any(self.protected(v) for v in [asset.asset_id, *asset.aliases, *asset.addresses])
        ):
            raise ServiceError("DENIED_PROTECTED_TARGET", 403)
        if asset and not asset.role and not asset.lab_asset and canonical(asset.asset_id) not in self.lab_assets:
            raise ServiceError("asset_protection_metadata_incomplete", 403)
        if action_type == "BLOCK_IP":
            try:
                address = ipaddress.ip_address(target)
            except ValueError as exc:
                raise ServiceError("target_must_be_ip", 422) from exc
            if "%" in original_target or str(address) != original_target:
                raise ServiceError("target_must_be_canonical_ip", 422)
            if getattr(address, "ipv4_mapped", None):
                raise ServiceError("use_canonical_ipv4_target", 422)
            if set(parameters) - {"lab_only"} or ("lab_only" in parameters and parameters["lab_only"] is not True):
                raise ServiceError("invalid_action_parameters", 422)
        elif action_type == "SUSPEND_TEST_PROCESS":
            if asset is None:
                raise ServiceError("unknown_target_asset", 422)
            if not asset.lab_asset and canonical(asset.asset_id) not in self.lab_assets:
                raise ServiceError("registered_lab_asset_required", 403)
            if (
                set(parameters) != {"process_name", "lab_only"}
                or parameters["lab_only"] is not True
                or not isinstance(parameters["process_name"], str)
                or not re.fullmatch(r"test-[A-Za-z0-9_.-]{1,80}", parameters["process_name"])
            ):
                raise ServiceError("test_process_required", 422)
            target = canonical(asset.asset_id)
        else:
            raise ServiceError("unsupported_action", 422)
        return target
