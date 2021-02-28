from typing import Dict


class EFBSystemUser(Dict):
    uid: str
    name: str


class EFBGroupChat(Dict):
    channel: str
    uid: str
    name: str


class EFBPrivateChat(EFBGroupChat):
    alias: str


class EFBGroupMember(Dict):
    name: str
    uid: str
    alias: str


class MiraiFriend(Dict):
    id: int
    nickname: str
    remark: str


class MiraiGroup(Dict):
    id: int
    name: str


class MiraiMember(Dict):
    id: int
    name: str
    permission: str
    group: MiraiGroup
