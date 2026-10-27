from datetime import date

from sqlmodel import Session, SQLModel, create_engine

from app.models import (
    Bien,
    Gestionnaire,
    Locataire,
    MandatGestion,
    Occupation,
    OccupationLocataire,
    UniteLocative,
)
from app.models.enums import RoleMandat, TypeBien, TypeGarantie


def test_immeuble_avec_unites_mandat_et_occupation():
    engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        immeuble = Bien(
            type=TypeBien.IMMEUBLE,
            libelle="Immeuble Sedan",
            adresse_rue="1 rue Test",
            adresse_code_postal="08200",
            adresse_ville="Sedan",
        )
        unite = UniteLocative(bien=immeuble, libelle="Appt 1")
        session.add(immeuble)
        session.add(unite)

        pergent = Gestionnaire(nom="Pergent Immobilier")
        locagestion = Gestionnaire(nom="Locagestion")
        session.add(pergent)
        session.add(locagestion)
        session.commit()

        session.add(
            MandatGestion(
                unite_locative_id=unite.id,
                gestionnaire_id=pergent.id,
                role=RoleMandat.MISE_EN_LOCATION,
                date_debut=date(2024, 1, 1),
            )
        )
        session.add(
            MandatGestion(
                unite_locative_id=unite.id,
                gestionnaire_id=locagestion.id,
                role=RoleMandat.GESTION,
                date_debut=date(2024, 1, 1),
            )
        )

        locataire = Locataire(nom="Dupont", prenom="Jean", type_garantie=TypeGarantie.VISALE)
        session.add(locataire)
        session.commit()

        occupation = Occupation(
            unite_locative_id=unite.id,
            date_entree=date(2024, 2, 1),
            loyer_mensuel_hc=500,
        )
        session.add(occupation)
        session.commit()

        session.add(OccupationLocataire(occupation_id=occupation.id, locataire_id=locataire.id))
        session.commit()

        session.refresh(unite)
        roles = {m.role for m in unite.mandats}
        assert roles == {RoleMandat.MISE_EN_LOCATION, RoleMandat.GESTION}

        session.refresh(occupation)
        assert [ol.locataire.nom for ol in occupation.locataires] == ["Dupont"]
