# -*- coding: utf-8 -*-

from __future__ import unicode_literals
import json
from glob import glob
import sys

from sqlalchemy.orm.exc import MultipleResultsFound, NoResultFound

from database import transaction
from models.candidacy import Candidacy
from models.election import Election
from models.party import Party
from models.person import Person
from utils.nlp.structurizer import markup
from utils.nlp.utils.translit import translit


__all__ = ['insert_candidacies']


person_ids = {}
map_gender = {
        u'남': 'm',
        u'여': 'f',
        }

map_gender_int = {
        u'남': 1,
        u'여': 2,
        }


def insert_candidacies(files, age, date):
    with transaction() as session:
        for file_ in glob(files):
            with open(file_, 'r') as f:
                list_ = json.load(f)
            for record in list_:
                person_id = insert_person(session, record)
                insert_party(session, record)
                insert_election(session, age, date)
                insert_candidacy(session, record, person_id, date)

            # TODO: recalc order, size of party table
            # TODO: put cosponsorship
            # TODO: put pledges


def insert_person(session, r):
    person = guess_person(r)

    if person:
        extra_vars = json.loads(person.extra_vars)
        extra_vars.update(r)
        extra_vars['assembly']['19'] = r
        person.extra_vars = json.dumps(extra_vars)

    else:
        person_id = get_person_id(r)
        name_en = translit(r['name_kr'], 'ko', 'en', 'name')
        gender = map_gender[r['sex']]
        birthday = '%04d%02d%02d' % (
                int(r.get('birthyear', 0)),
                int(r.get('birthmonth', 0)),
                int(r.get('birthday', 0))
                )
        education = markup(r['education'], 'education')
        address = markup(r['address'], 'district')
        extra_vars = r.copy()
        extra_vars['assembly'] = {}
        extra_vars['assembly']['19'] = r

        person = Person(
                id=person_id,
                name=r['name_kr'],
                name_en=name_en,
                name_cn=r['name_cn'],
                gender=gender,
                birthday=birthday,
                education=[term[0] for term in education],
                education_id=[term[1] for term in education],
                address=[term[0] for term in address],
                address_id=[term[1] for term in address],
                image=r.get('image', None),
                twitter=r.get('twitter', None),
                facebook=r.get('facebook', None),
                blog=r.get('blog', None),
                homepage=r.get('homepage', None),
                extra_vars=json.dumps(extra_vars)
                )

        session.add(person)
        session.flush()

    return person.id


def insert_party(session, r):
    name = r['party']
    if name and not has_party(session, name):
        party = Party(name=name)
        session.add(party)
        session.flush()


def insert_election(session, age, date):
    if not has_election(session, age=age, date=date, type='assembly'):
        election = Election('assembly', age, date=date, is_regular=False)
        session.add(election)
        session.flush()


def insert_candidacy(session, r, person_id, date):
    election_id = get_election_id(session, date)
    party_id = get_party(session, r['party']).id
    district = markup(r['district'], 'district')
    candidacy = Candidacy(
            person_id=person_id,
            election_id=election_id,
            party_id=party_id,
            is_elected=r['elected'],
            cand_no=to_int(r.get('cand_no', 0)),
            vote_score=to_int(r.get('votenum', 0)),
            vote_share=to_float(r.get('voterate', 0)),
            district=[term[0] for term in district],
            district_id=[term[1] for term in district],
            )
    session.add(candidacy)


def to_int(num):
    if type(num) != int and (not hasattr(num, 'isdigit') or not num.isdigit()):
        return 0
    return int(num)


def to_float(num):
    if type(num) not in [int, float]\
            and (not hasattr(num, 'isdigit') or not num.isdigit()):
        return 0
    return float(num)


def has_election(session, type, age, date):
    return session.query(Election)\
            .filter_by(age=age, date=date, type='assembly').count() > 0


def guess_person(r):
    r['name_kr'] = r['name_kr'].replace(' ', '')

    try:
        person = Person.query.filter_by(name=r['name_kr'],
                                        birthday_year=r['birthyear']).one()
    except (MultipleResultsFound, NoResultFound):
        person = None

    return person


def get_person(session, person_id):
    return session.query(Person).filter_by(id=person_id).one()


def get_person_id(person):
    gender = map_gender[person['sex']]
    count = Person.query.filter_by(gender=gender,
                                   birthday_year=person['birthyear']).count() + 1
    key_part = '%s%d' % (person['birthyear'], map_gender_int[person['sex']])
    return int('%s%d' % (key_part, count))


def has_party(session, name):
    return session.query(Party).filter_by(name=name).count() > 0


def get_party(session, name):
    party = session.query(Party)\
            .filter_by(name=name).one()
    return party


def get_election_id(session, date):
    election = session.query(Election)\
            .filter_by(type='assembly', date=date).one()
    return election.id

