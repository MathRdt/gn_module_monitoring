"""
    Modèles SQLAlchemy pour les modules de suivi
"""
from flask import g
from sqlalchemy import join, select, func, and_, or_, false
from sqlalchemy.inspection import inspect
from sqlalchemy.sql import case
from sqlalchemy.orm import (
    column_property,
    ColumnProperty,
    RelationshipProperty,
    class_mapper,
    aliased,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from uuid import uuid4

from utils_flask_sqla.serializers import serializable
from utils_flask_sqla_geo.serializers import geoserializable

from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.ext.declarative import declared_attr

from pypnnomenclature.models import TNomenclatures, BibNomenclaturesTypes
from geonature.core.gn_commons.models import TMedias
from geonature.core.gn_monitoring.models import TBaseSites, TBaseVisits
from geonature.core.gn_meta.models import TDatasets
from geonature.utils.env import DB
from geonature.core.gn_commons.models import TModules, cor_module_dataset
from pypnusershub.db.models import User
from geonature.core.gn_monitoring.models import corVisitObserver
from gn_module_monitoring.monitoring.queries import (
    Query as MonitoringQuery,
    SitesQuery,
    SitesGroupsQuery,
    VisitQuery,
    ObservationsQuery,
)
from geonature.core.gn_permissions.tools import has_any_permissions_by_action

# from geoalchemy2 import Geometry
import geoalchemy2


class GenericModel:
    @declared_attr
    def __tablename__(cls):
        return cls.__name__.lower()

    @classmethod
    def set_id(cls) -> None:
        pk_string = class_mapper(cls).primary_key[0].name
        if hasattr(cls, "id_g") == False:
            pk_value = getattr(cls, pk_string)
            setattr(cls, "id_g", pk_value)

    @classmethod
    def get_id_name(cls) -> None:
        pk_string = class_mapper(cls).primary_key[0].name
        # print('======= ==>', pk_string)
        if hasattr(cls, "id_g") == False:
            pk_value = getattr(cls, pk_string)
            setattr(cls, "id_g", pk_value)
        return pk_string

    @classmethod
    def find_by_id(cls, _id: int) -> "GenericModel":
        cls.set_id()
        return cls.query.get_or_404(_id)

    @classmethod
    def attribute_names(cls):
        return [
            prop.key
            for prop in class_mapper(cls).iterate_properties
            if isinstance(prop, ColumnProperty)
        ]

    # TODO: Voir si on garde cette méthode pour simplifier la recherche des relationship lors des filtres
    @classmethod
    def attribute_names_relationship(cls):
        relationship_cols = inspect(cls).relationships.items()
        return relationship_cols
        # return [ cols[0] for cols in relationship_cols]
        # return [
        #     prop.key
        #     for prop in class_mapper(cls).iterate_properties
        #     if isinstance(prop, RelationshipProperty)
        # ]


class PermissionModel(GenericModel):
    def has_permission(
        self,
        cruved_object={"C": False, "R": False, "U": False, "D": False, "E": False, "V": False},
    ):
        cruved_object_out = {}
        for action_key, action_value in cruved_object.items():
            cruved_object_out[action_key] = self.has_instance_permission(scope=action_value)
        return cruved_object_out

    def get_permission_by_action(self, module_code=None, object_code=None):
        return has_any_permissions_by_action(module_code=module_code, object_code=object_code)


cor_module_type = DB.Table(
    "cor_module_type",
    DB.Column(
        "id_module",
        DB.Integer,
        DB.ForeignKey("gn_commons.t_modules.id_module"),
        primary_key=True,
    ),
    DB.Column(
        "id_type_site",
        DB.Integer,
        DB.ForeignKey("gn_monitoring.bib_type_site.id_nomenclature_type_site"),
        primary_key=True,
    ),
    schema="gn_monitoring",
)

cor_type_site = DB.Table(
    "cor_type_site",
    DB.Column(
        "id_base_site",
        DB.Integer,
        DB.ForeignKey("gn_monitoring.t_base_sites.id_base_site"),
        primary_key=True,
    ),
    DB.Column(
        "id_type_site",
        DB.Integer,
        DB.ForeignKey("gn_monitoring.bib_type_site.id_nomenclature_type_site"),
        primary_key=True,
    ),
    schema="gn_monitoring",
)


@serializable
class BibTypeSite(DB.Model, PermissionModel):
    __tablename__ = "bib_type_site"
    __table_args__ = {"schema": "gn_monitoring"}
    query_class = MonitoringQuery

    id_nomenclature_type_site = DB.Column(
        DB.ForeignKey("ref_nomenclatures.t_nomenclatures.id_nomenclature"),
        nullable=False,
        primary_key=True,
    )
    config = DB.Column(JSONB)
    nomenclature = DB.relationship(
        TNomenclatures, uselist=False, backref=DB.backref("bib_type_site", uselist=False)
    )

    sites = DB.relationship("TMonitoringSites", secondary=cor_type_site, lazy="noload")


@serializable
class TMonitoringObservationDetails(DB.Model):
    __tablename__ = "t_observation_details"
    __table_args__ = {"schema": "gn_monitoring"}

    id_observation_detail = DB.Column(DB.Integer, primary_key=True, nullable=False, unique=True)

    id_observation = DB.Column(DB.ForeignKey("gn_monitoring.t_observations.id_observation"))
    data = DB.Column(JSONB)
    uuid_observation_detail = DB.Column(UUID(as_uuid=True), default=uuid4)

    medias = DB.relationship(
        TMedias,
        lazy="joined",
        primaryjoin=(TMedias.uuid_attached_row == uuid_observation_detail),
        foreign_keys=[TMedias.uuid_attached_row],
    )


@serializable
class TObservations(DB.Model, PermissionModel):
    __tablename__ = "t_observations"
    __table_args__ = {"schema": "gn_monitoring"}
    id_observation = DB.Column(DB.Integer, primary_key=True, nullable=False, unique=True)
    id_base_visit = DB.Column(DB.ForeignKey("gn_monitoring.t_base_visits.id_base_visit"))
    id_digitiser = DB.Column(DB.Integer, DB.ForeignKey("utilisateurs.t_roles.id_role"))
    digitiser = DB.relationship(
        User, primaryjoin=(User.id_role == id_digitiser), foreign_keys=[id_digitiser]
    )
    cd_nom = DB.Column(DB.Integer)
    comments = DB.Column(DB.String)
    uuid_observation = DB.Column(UUID(as_uuid=True), default=uuid4)

    medias = DB.relationship(
        TMedias,
        lazy="joined",
        primaryjoin=(TMedias.uuid_attached_row == uuid_observation),
        foreign_keys=[TMedias.uuid_attached_row],
    )

    observation_details = DB.relation(
        TMonitoringObservationDetails,
        primaryjoin=(id_observation == TMonitoringObservationDetails.id_observation),
        foreign_keys=[TMonitoringObservationDetails.id_observation],
        cascade="all,delete",
    )


@serializable
class TMonitoringObservations(TObservations, PermissionModel):
    __tablename__ = "t_observation_complements"
    __table_args__ = {"schema": "gn_monitoring"}
    __mapper_args__ = {
        "polymorphic_identity": "monitoring_observation",
    }

    query_class = ObservationsQuery

    data = DB.Column(JSONB)

    id_observation = DB.Column(
        DB.ForeignKey("gn_monitoring.t_observations.id_observation"),
        primary_key=True,
        nullable=False,
    )

    @hybrid_property
    def organism_actors(self):
        # return self.digitiser.id_organisme
        actors_organism_list = []
        if isinstance(self.digitiser, list):
            for actor in self.digitiser:
                if actor.id_organisme is not None:
                    actors_organism_list.append(actor.id_organisme)
        elif isinstance(self.digitiser, User):
            actors_organism_list.append(self.digitiser.id_organisme)
        else:
            return
        return actors_organism_list

    def has_instance_permission(self, scope):
        if scope == 0:
            return False
        elif scope in (1, 2):
            if (
                g.current_user.id_role == self.id_digitiser
            ):  # or g.current_user in self.user_actors:
                return True
            if scope == 2 and g.current_user.organisme in self.organism_actors:
                return True
        elif scope == 3:
            return True


TBaseVisits.dataset = DB.relationship(TDatasets)


@serializable
class TMonitoringVisits(TBaseVisits, PermissionModel):
    __tablename__ = "t_visit_complements"
    __table_args__ = {"schema": "gn_monitoring"}
    __mapper_args__ = {
        "polymorphic_identity": "monitoring_visit",
    }
    query_class = VisitQuery
    id_base_visit = DB.Column(
        DB.ForeignKey("gn_monitoring.t_base_visits.id_base_visit"),
        nullable=False,
        primary_key=True,
    )

    data = DB.Column(JSONB)

    medias = DB.relationship(
        TMedias,
        lazy="joined",
        primaryjoin=(TMedias.uuid_attached_row == TBaseVisits.uuid_base_visit),
        foreign_keys=[TMedias.uuid_attached_row],
    )

    observers = DB.relationship(User, lazy="joined", secondary=corVisitObserver)

    observations = DB.relation(
        "TMonitoringObservations",
        lazy="select",
        primaryjoin=(TObservations.id_base_visit == TBaseVisits.id_base_visit),
        foreign_keys=[TObservations.id_base_visit],
        cascade="all,delete",
    )

    nb_observations = column_property(
        select([func.count(TObservations.id_base_visit)]).where(
            TObservations.id_base_visit == id_base_visit
        )
    )

    module = DB.relationship(
        TModules,
        lazy="select",
        primaryjoin=(TModules.id_module == TBaseVisits.id_module),
        foreign_keys=[TBaseVisits.id_module],
        uselist=False,
    )

    @hybrid_property
    def organism_actors(self):
        # return self.digitiser.id_organisme
        actors_organism_list = []
        if isinstance(self.digitiser, list):
            for actor in self.digitiser:
                if actor.id_organisme is not None:
                    actors_organism_list.append(actor.id_organisme)
        elif isinstance(self.observers, list):
            for actor in self.observers:
                if actor.id_organisme is not None:
                    actors_organism_list.append(actor.id_organisme)
        elif isinstance(self.digitiser, User):
            actors_organism_list.append(self.digitiser.id_organisme)
        else:
            return actors_organism_list
        return actors_organism_list

    def has_instance_permission(self, scope):
        if scope == 0:
            return False
        elif scope in (1, 2):
            if g.current_user.id_role == self.id_digitiser or any(
                observer.id_role == g.current_user.id_role for observer in self.observers
            ):  # or g.current_user in self.user_actors:
                return True
            if scope == 2 and g.current_user.organisme in self.organism_actors:
                return True
        elif scope == 3:
            return True


@geoserializable(geoCol="geom", idCol="id_base_site")
class TMonitoringSites(TBaseSites, PermissionModel):
    __tablename__ = "t_site_complements"
    __table_args__ = {"schema": "gn_monitoring"}
    __mapper_args__ = {
        "polymorphic_identity": "monitoring_site",
    }
    query_class = SitesQuery

    id_base_site = DB.Column(
        DB.ForeignKey("gn_monitoring.t_base_sites.id_base_site"), nullable=False, primary_key=True
    )

    id_sites_group = DB.Column(
        DB.ForeignKey(
            "gn_monitoring.t_sites_groups.id_sites_group",
            # ondelete='SET NULL'
        ),
        nullable=False,
    )

    data = DB.Column(JSONB)

    visits = DB.relationship(
        TMonitoringVisits,
        lazy="select",
        primaryjoin=(TBaseSites.id_base_site == TBaseVisits.id_base_site),
        foreign_keys=[TBaseVisits.id_base_site],
        cascade="all,delete",
    )

    medias = DB.relationship(
        TMedias,
        lazy="joined",
        primaryjoin=(TMedias.uuid_attached_row == TBaseSites.uuid_base_site),
        foreign_keys=[TMedias.uuid_attached_row],
        cascade="all",
    )

    last_visit = column_property(
        select([func.max(TBaseVisits.visit_date_min)]).where(
            TBaseVisits.id_base_site == id_base_site
        )
    )

    nb_visits = column_property(
        select([func.count(TBaseVisits.id_base_site)]).where(
            TBaseVisits.id_base_site == id_base_site
        )
    )

    geom_geojson = column_property(
        select([func.st_asgeojson(TBaseSites.geom)])
        .where(TBaseSites.id_base_site == id_base_site)
        .correlate_except(TBaseSites)
    )
    types_site = DB.relationship("BibTypeSite", secondary=cor_type_site, lazy="joined")

    @hybrid_property
    def organism_actors(self):
        # return self.inventor.id_organisme
        actors_organism_list = []
        if isinstance(self.inventor, list):
            for actor in self.inventor:
                if actor.id_organisme is not None:
                    actors_organism_list.append(actor.id_organisme)
        else:
            if hasattr(self.inventor, "id_organisme"):
                actors_organism_list.append(self.inventor.id_organisme)

    def has_instance_permission(self, scope):
        if scope == 0:
            return False
        elif scope in (1, 2):
            if (
                g.current_user.id_role == self.id_digitiser
                or g.current_user.id_role == self.id_inventor
            ):  # or g.current_user in self.user_actors:
                return True
            if scope == 2 and g.current_user.organisme in self.organism_actors:
                return True
        elif scope == 3:
            return True


@geoserializable(geoCol="geom", idCol="id_sites_group")
class TMonitoringSitesGroups(DB.Model, PermissionModel):
    __tablename__ = "t_sites_groups"
    __table_args__ = {"schema": "gn_monitoring"}
    query_class = SitesGroupsQuery

    id_sites_group = DB.Column(DB.Integer, primary_key=True, nullable=False, unique=True)
    id_digitiser = DB.Column(DB.Integer, DB.ForeignKey("utilisateurs.t_roles.id_role"))

    digitiser = DB.relationship(
        User, primaryjoin=(User.id_role == id_digitiser), foreign_keys=[id_digitiser]
    )
    uuid_sites_group = DB.Column(UUID(as_uuid=True), default=uuid4)

    sites_group_name = DB.Column(DB.Unicode)
    sites_group_code = DB.Column(DB.Unicode)
    sites_group_description = DB.Column(DB.Unicode)

    comments = DB.Column(DB.Unicode)
    geom = DB.Column(geoalchemy2.types.Geometry("GEOMETRY", 4326, nullable=True))
    data = DB.Column(JSONB)

    medias = DB.relationship(
        TMedias,
        primaryjoin=(TMedias.uuid_attached_row == uuid_sites_group),
        foreign_keys=[TMedias.uuid_attached_row],
        lazy="joined",
    )

    sites = DB.relationship(
        TMonitoringSites,
        uselist=True,  # pourquoi pas par defaut ?
        primaryjoin=(TMonitoringSites.id_sites_group == id_sites_group),
        foreign_keys=[TMonitoringSites.id_sites_group],
        lazy="joined",
    )

    nb_sites = column_property(
        select([func.count(TMonitoringSites.id_sites_group)]).where(
            TMonitoringSites.id_sites_group == id_sites_group
        )
    )

    altitude_min = DB.Column(DB.Integer)
    altitude_max = DB.Column(DB.Integer)
    nb_visits = column_property(
        select([func.count(TMonitoringVisits.id_base_site)]).where(
            and_(
                TMonitoringVisits.id_base_site == TMonitoringSites.id_base_site,
                TMonitoringSites.id_sites_group == id_sites_group,
            )
        )
    )

    # @hybrid_property
    # def geom_geojson(self):
    #     if self.geom is None:
    #         return column_property(
    #             select([func.st_asgeojson(func.st_convexHull(func.st_collect(TBaseSites.geom)))])
    #             .select_from(
    #                 self.__table__.alias("subquery").join(
    #                     TMonitoringSites,
    #                     TMonitoringSites.id_sites_group == self.id_sites_group,
    #                 )
    #             )
    #             .where(
    #                 TMonitoringSites.id_sites_group == self.id_sites_group,
    #             )
    #     )
    #     else:
    #         return column_property(
    #         select([func.st_asgeojson(self.geom)])
    #         )

    @hybrid_property
    def organism_actors(self):
        # return self.digitiser.id_organisme
        actors_organism_list = []
        if isinstance(self.digitiser, list):
            for actor in self.digitiser:
                if actor.id_organisme is not None:
                    actors_organism_list.append(actor.id_organisme)
        elif isinstance(self.digitiser, User):
            actors_organism_list.append(self.digitiser.id_organisme)
        else:
            return
        return actors_organism_list

    def has_instance_permission(self, scope):
        if scope == 0:
            return False
        elif scope in (1, 2):
            if (
                g.current_user.id_role == self.id_digitiser
            ):  # or g.current_user in self.user_actors:
                return True
            if scope == 2 and g.current_user.organisme in self.organism_actors:
                return True
        elif scope == 3:
            return True


@serializable
class TMonitoringModules(TModules, PermissionModel):
    __tablename__ = "t_module_complements"
    __table_args__ = {"schema": "gn_monitoring"}
    __mapper_args__ = {
        "polymorphic_identity": "monitoring_module",
    }
    query_class = MonitoringQuery

    id_module = DB.Column(
        DB.ForeignKey("gn_commons.t_modules.id_module"),
        primary_key=True,
        nullable=False,
        unique=True,
    )

    uuid_module_complement = DB.Column(UUID(as_uuid=True), default=uuid4)

    id_list_observer = DB.Column(DB.Integer)
    id_list_taxonomy = DB.Column(DB.Integer)

    taxonomy_display_field_name = DB.Column(DB.Unicode)
    b_synthese = DB.Column(DB.Boolean)
    b_draw_sites_group = DB.Column(DB.Boolean)

    medias = DB.relationship(
        TMedias,
        primaryjoin=(TMedias.uuid_attached_row == uuid_module_complement),
        foreign_keys=[TMedias.uuid_attached_row],
        lazy="joined",
    )

    # TODO: restore it with CorCategorySite
    # sites = DB.relationship(
    #     'TMonitoringSites',
    #     uselist=True,  # pourquoi pas par defaut ?
    #     primaryjoin=TMonitoringSites.id_module == id_module,
    #     foreign_keys=[id_module],
    #     lazy="select",
    # )

    # sites_groups = DB.relationship(
    #     'TMonitoringSitesGroups',
    #     uselist=True,  # pourquoi pas par defaut ?
    #     primaryjoin=TMonitoringSitesGroups.id_module == id_module,
    #     foreign_keys=[id_module],
    #     lazy="select",
    # )

    datasets = DB.relationship(
        "TDatasets",
        secondary=cor_module_dataset,
        join_depth=0,
        lazy="joined",
    )

    types_site = DB.relationship("BibTypeSite", secondary=cor_module_type, lazy="joined")

    data = DB.Column(JSONB)

    # visits = DB.relationship(
    #     TMonitoringVisits,
    #     lazy="select",
    #     primaryjoin=(TModules.id_module == TBaseVisits.id_module),
    #     foreign_keys=[TBaseVisits.id_module],
    #     cascade="all,delete"
    # )


# Use alias since there is already a FROM caused by count (column_properties)
sites_alias = aliased(TMonitoringSites)
TMonitoringModules.sites_groups = DB.relationship(
    "TMonitoringSitesGroups",
    uselist=True,  # pourquoi pas par defaut ?
    primaryjoin=TMonitoringModules.id_module == cor_module_type.c.id_module,
    secondaryjoin=and_(
        TMonitoringSitesGroups.id_sites_group == sites_alias.id_sites_group,
        sites_alias.id_base_site == cor_type_site.c.id_base_site,
    ),
    secondary=join(
        cor_type_site,
        cor_module_type,
        cor_type_site.c.id_type_site == cor_module_type.c.id_type_site,
    ),
    foreign_keys=[cor_type_site.c.id_base_site, cor_module_type.c.id_module],
    lazy="select",
    viewonly=True,
)


TMonitoringModules.sites = DB.relationship(
    "TMonitoringSites",
    uselist=True,  # pourquoi pas par defaut ?
    primaryjoin=TMonitoringModules.id_module == cor_module_type.c.id_module,
    secondaryjoin=TMonitoringSites.id_base_site == cor_type_site.c.id_base_site,
    secondary=join(
        cor_type_site,
        cor_module_type,
        cor_type_site.c.id_type_site == cor_module_type.c.id_type_site,
    ),
    foreign_keys=[cor_type_site.c.id_base_site, cor_module_type.c.id_module],
    lazy="select",
    viewonly=True,
)

TMonitoringModules.visits = DB.relationship(
    TMonitoringVisits,
    lazy="select",
    primaryjoin=(TMonitoringModules.id_module == TMonitoringVisits.id_module),
    foreign_keys=[TMonitoringVisits.id_module],
    cascade="all",
)


# add sites_group relationship to TMonitoringSites

TMonitoringSites.sites_group = DB.relationship(
    TMonitoringSitesGroups,
    primaryjoin=(TMonitoringSitesGroups.id_sites_group == TMonitoringSites.id_sites_group),
    cascade="all",
    lazy="select",
    uselist=False,
)

TMonitoringSitesGroups.visits = DB.relationship(
    TMonitoringVisits,
    primaryjoin=(TMonitoringSites.id_sites_group == TMonitoringSitesGroups.id_sites_group),
    secondaryjoin=(TMonitoringVisits.id_base_site == TMonitoringSites.id_base_site),
    secondary="gn_monitoring.t_site_complements",
)

TMonitoringSitesGroups.nb_visits = column_property(
    select([func.count(TMonitoringVisits.id_base_site)]).where(
        and_(
            TMonitoringVisits.id_base_site == TMonitoringSites.id_base_site,
            TMonitoringSites.id_sites_group == TMonitoringSitesGroups.id_sites_group,
        )
    )
)

# note the alias is mandotory otherwise the where is done on the subquery table
# and not the global TMonitoring table
TMonitoringSitesGroups.geom_geojson = column_property(
    select([func.st_asgeojson(func.st_convexHull(func.st_collect(TBaseSites.geom)))])
    .select_from(
        TMonitoringSitesGroups.__table__.alias("subquery").join(
            TMonitoringSites,
            TMonitoringSites.id_sites_group == TMonitoringSitesGroups.id_sites_group,
        )
    )
    .where(
        TMonitoringSites.id_sites_group == TMonitoringSitesGroups.id_sites_group,
    )
)

# case([(TMonitoringSitesGroups.geom is None, select([func.st_asgeojson(func.st_convexHull(func.st_collect(TBaseSites.geom)))])
#             .select_from(
#                 TMonitoringSitesGroups.__table__.alias("subquery").join(
#                     TMonitoringSites,
#                     TMonitoringSites.id_sites_group == TMonitoringSitesGroups.id_sites_group,
#                 )
#             )
#             .where(
#                 TMonitoringSites.id_sites_group == TMonitoringSitesGroups.id_sites_group,
#             )), (TMonitoringSitesGroups.geom is not None,select([func.st_asgeojson(TMonitoringSitesGroups.geom)]))]))
