from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, TypedDict

import requests
from django.conf import settings
from django.core.exceptions import FieldDoesNotExist, ValidationError
from django.db import transaction
from django.db.utils import DEFAULT_DB_ALIAS

from core.enums import ObjectChangeAction
from net.models import Connection
from peering.models import InternetExchange as Ixp

from .models import (
    BaseModel,
    Campus,
    Carrier,
    CarrierFacility,
    Facility,
    InternetExchange,
    InternetExchangeFacility,
    IXLan,
    IXLanPrefix,
    Network,
    NetworkContact,
    NetworkFacility,
    NetworkIXLan,
    Organization,
    Synchronisation,
)

__all__ = ("NAMESPACES", "PeeringDB")

# Order matters for caching data locally
NAMESPACES = {
    "org": Organization,
    "campus": Campus,
    "fac": Facility,
    "carrier": Carrier,
    "carrierfac": CarrierFacility,
    "net": Network,
    "ix": InternetExchange,
    "ixfac": InternetExchangeFacility,
    "ixlan": IXLan,
    "ixpfx": IXLanPrefix,
    "netfac": NetworkFacility,
    "netixlan": NetworkIXLan,
    "poc": NetworkContact,
}

logger = logging.getLogger("peering.manager.peeringdb")


class SyncChanges(TypedDict):
    created: int
    updated: int
    deleted: int


class PeeringDB:
    """
    Class used to interact with the PeeringDB API.
    """

    def __init__(self):
        self._caching_timestamps: list[datetime] = []

    def lookup(self, namespace: str, search: dict[str, int]) -> dict[str, Any] | None:
        """
        Sends a get request to the API given a namespace and some parameters.
        """
        # Enforce trailing slash and add namespace
        api_url = f"{settings.PEERINGDB_API.strip('/')}/{namespace}"

        # Check if the depth param is provided, add it if not
        if "depth" not in search:
            search["depth"] = 1

        # Authenticate with API Key if present
        q = {
            "headers": {"User-Agent": settings.REQUESTS_USER_AGENT},
            "params": search,
        }

        if settings.PEERINGDB_API_KEY:
            q["headers"]["AUTHORIZATION"] = f"Api-Key {settings.PEERINGDB_API_KEY}"
        # To be removed in v2.0
        elif settings.PEERINGDB_USERNAME:
            logger.warning(
                "PeeringDB authentication with username/password is deprecated and will be removed in v2.0. Please use an API key instead."
            )
            q["auth"] = (settings.PEERINGDB_USERNAME, settings.PEERINGDB_PASSWORD)

        # Make the request
        logger.debug(f"calling api: {api_url} | {search}")
        response = requests.get(api_url, **q, proxies=settings.HTTP_PROXIES)

        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            logger.error(e)
            return None

        return response.json()

    def record_last_sync(
        self, time: int, changes: SyncChanges
    ) -> Synchronisation | None:
        """
        Saves the last synchronisation details (number of objects and time) for later
        use (and logs).
        """
        last_sync = None
        changes_number = changes["created"] + changes["updated"] + changes["deleted"]

        # Save the last sync time only if objects were retrieved
        if changes_number > 0:
            last_sync = Synchronisation(
                time=time,
                created=changes["created"],
                updated=changes["updated"],
                deleted=changes["deleted"],
            )
            last_sync.save()

            logger.debug(f"synchronised {changes_number} objects at {last_sync.time}")

        return last_sync

    def get_last_synchronisation_for_model(self, model: type[BaseModel]) -> int:
        """
        Returns the last synchronisation time for a given model. The time is based on
        the latest record updated field.
        """
        try:
            time = model.objects.latest("updated").updated.timestamp()
        except model.DoesNotExist:
            time = 0

        return int(time)

    def get_last_synchronisation(self) -> Synchronisation | None:
        """
        Returns the last recorded synchronisation.
        """
        try:
            return Synchronisation.objects.latest("time")
        except Synchronisation.DoesNotExist:
            return None

    def _process_field(
        self,
        model: type[BaseModel],
        foreign_keys: list[str],
        obj: BaseModel,
        name: str,
        value: Any,
    ):
        """
        Sets the value for a single field of an object.
        """
        # Fields not to process
        if name == "status" or (
            hasattr(obj, "ignored_fields") and name in model.ignored_fields
        ):
            return

        # If the field looks like one of the FK
        for f in foreign_keys:
            if f in name:
                # Handle special case where PeeringDB does not suffix with _id
                if f in {"net_side", "ix_side"}:
                    name = f"{f}_id"
                # The field is the FK ID so set it
                if name == f"{f}_id":
                    setattr(obj, name, value)
                # If the field starts with a foreign key name but is not
                # suffixed by _id, just ignore it (it can be its name or
                # something else)
                return

        try:
            # Latitude and longitude are special decimal values that must be
            # casted to string before using them
            if name in {"latitude", "longitude"} and value is not None:
                value = str(value)

            setattr(obj, name, value)
        except FieldDoesNotExist:
            logger.error(
                f"field: {name} not in model: {model._meta.verbose_name.lower()}"
            )

    def _process_object(
        self, model: type[BaseModel], data: dict[str, Any]
    ) -> tuple[BaseModel, ObjectChangeAction]:
        """
        Synchronises a single object.
        """
        action = (
            ObjectChangeAction.DELETE
            if data["status"] == "deleted"
            else ObjectChangeAction.UPDATE
        )

        try:
            # Get the local object by its ID
            local_object = model.objects.get(pk=data["id"])

            # Object marked as deleted so remove it locally too
            if action == ObjectChangeAction.DELETE:
                logger.debug(
                    f"deleted {model._meta.verbose_name.lower()} #{local_object.pk} from local database"
                )
                local_object.delete()
                return None, action
        except model.DoesNotExist:
            action = ObjectChangeAction.CREATE
            local_object = model()

        # Make a list of foreign key field names
        fk = [
            f.name
            for f in model._meta.get_fields()
            if f.get_internal_type() == "ForeignKey"
        ]

        # Set the value for each field
        for field_name, field_value in data.items():
            self._process_field(model, fk, local_object, field_name, field_value)

        return local_object, action

    def _fix_related_objects(self) -> None:
        """
        Fixes main connections and IXPs objects linking them with PeeringDB's if
        possible.
        """
        for c in Connection.objects.all():
            c.link_to_peeringdb()
        for i in Ixp.objects.all():
            i.link_to_peeringdb()

    def synchronise_objects(
        self, namespace: str, model: type[BaseModel]
    ) -> tuple[int, int, int]:
        """
        Synchronises all the objects of a namespace of the PeeringDB to the
        local database. This function is meant to be run regularly to update
        the local database with the latest changes.

        If the object already exists locally it will be updated and no new
        entry will be created.

        If the object is marked as deleted in the PeeringDB, it will be deleted
        locally as well.

        This function returns the number of objects that have been successfully
        synchronised to the local database.
        """
        created, updated, deleted = 0, 0, 0

        # Get all changes since the last sync
        search = {"since": self.get_last_synchronisation_for_model(model), "depth": 0}
        result = self.lookup(namespace, search)

        if not result:
            return (created, updated, deleted)

        if "generated" in result["meta"]:
            peeringdb_cache_timestamp = datetime.fromtimestamp(
                result["meta"]["generated"], tz=timezone.utc
            )
            self._caching_timestamps.append(peeringdb_cache_timestamp)
            logger.debug(f"peeringdb {namespace} cached at {peeringdb_cache_timestamp}")

        for data in result["data"]:
            local_object, action = self._process_object(model, data)

            try:
                if local_object:
                    local_object.full_clean()
                    local_object.save()
            except ValidationError as e:
                logger.error(
                    f"error validating id: {local_object.id} for model: {model._meta.verbose_name.lower()}\n{e}"
                )
                continue

            match action:
                case ObjectChangeAction.CREATE:
                    created += 1
                    logger.debug(
                        f"created {model._meta.verbose_name.lower()} #{local_object.pk} from peeringdb"
                    )
                case ObjectChangeAction.UPDATE:
                    updated += 1
                    logger.debug(
                        f"updated {model._meta.verbose_name.lower()} #{local_object.pk} from peeringdb"
                    )
                case ObjectChangeAction.DELETE:
                    deleted += 1

        return (created, updated, deleted)

    def update_local_database(self) -> Synchronisation | None:
        """
        Updates the local database by synchronising all PeeringDB API's namespaces
        that we are caring about.
        """
        list_of_changes: list[tuple[int, int, int]] = []

        # Try to sync objects
        for namespace, object_type in NAMESPACES.items():
            # Make a single transaction, avoid too much database commits (poor
            # speed) and fail the whole synchronisation if something goes wrong
            with transaction.atomic():
                changes = self.synchronise_objects(namespace, object_type)
                list_of_changes.append(changes)

            self._fix_related_objects()

        objects_changes = SyncChanges(
            created=sum(created for created, _, _ in list_of_changes),
            updated=sum(updated for _, updated, _ in list_of_changes),
            deleted=sum(deleted for _, _, deleted in list_of_changes),
        )

        # Save the last sync time based on the oldest PeeringDB cache timestamp
        last_sync_at = min(
            self._caching_timestamps, default=datetime.now(tz=timezone.utc)
        )
        logger.debug(f"last peeringdb synchronisation time set at {last_sync_at}")
        return self.record_last_sync(last_sync_at, objects_changes)

    def clear_local_database(self) -> None:
        """
        Deletes all data related to the local database. This can be used to get a
        fresh start.
        """
        # Unlink main objects from PeeringDB's before emptying the local database
        Connection.objects.filter(peeringdb_netixlan__isnull=False).update(
            peeringdb_netixlan=None
        )
        Ixp.objects.filter(peeringdb_ixlan__isnull=False).update(peeringdb_ixlan=None)

        # The use of reversed is important to avoid fk issues
        for model in reversed(list(NAMESPACES.values())):
            model.objects.all()._raw_delete(using=DEFAULT_DB_ALIAS)
        Synchronisation.objects.all()._raw_delete(using=DEFAULT_DB_ALIAS)
