# coding: utf-8
import asyncio
import functools
import logging
from asyncio import Future
from traceback import print_exc
from typing import Collection, BinaryIO, Dict, Any, List, Union

from cachetools import TTLCache
from efb_qq_slave import BaseClient
from ehforwarderbot import Chat, Status, coordinator, MsgType, Message
from ehforwarderbot.exceptions import EFBOperationNotSupported
from ehforwarderbot.types import ChatID

from mirai_core import Bot, Updater
from mirai_core.models import Message as MiraiMessage
from mirai_core.models import Event, Types
from mirai_core.models.Entity import Friend, Group, Member
from mirai_core.models.Message import At, Plain, BaseMessageComponent, BotMessage, Image
from mirai_core.models.Types import MessageType
from mirai_core.updater import Shutdown

from efb_qq_plugin_mirai.ChatMgr import ChatMgr
from efb_qq_plugin_mirai.CustomTypes import EFBGroupChat, EFBPrivateChat, MiraiFriend, MiraiGroup, EFBGroupMember, \
    MiraiMember
from efb_qq_plugin_mirai.MiraiConfig import MiraiConfig
from efb_qq_plugin_mirai.MiraiFactory import MiraiFactory
from efb_qq_plugin_mirai.MiraiMessageProcessor import MiraiMessageProcessor
from efb_qq_plugin_mirai.MsgDecorator import efb_text_simple_wrapper
from efb_qq_plugin_mirai.Utils import process_quote_text, download_user_avatar, download_group_avatar
import threading


class mirai(BaseClient):
    client_name: str = "Mirai Client"
    client_id: str = "mirai"
    client_config: Dict[str, Any]

    info_list = TTLCache(maxsize=2, ttl=600)

    info_dict = TTLCache(maxsize=2, ttl=600)

    group_member_list = TTLCache(maxsize=100, ttl=3600)
    stranger_cache = TTLCache(maxsize=100, ttl=3600)
    shutdown_hook = None
    logger: logging.Logger = logging.getLogger(__name__)

    def __init__(self, client_id: str, config: Dict[str, Any], channel):
        super().__init__(client_id, config)
        self.client_config = config[self.client_id]
        MiraiConfig.configs = self.client_config
        self.uin = self.client_config['qq']
        self.host = self.client_config['host']
        self.port = self.client_config['port']
        self.authKey = self.client_config['authKey']
        self.scheme = self.client_config.get('scheme') or 'http'
        self.loop = asyncio.get_event_loop()
        self.bot = Bot(self.uin, self.client_config['host'], self.client_config['port'], self.authKey, self.loop, self.scheme)
        self.updater = Updater(self.bot)
        self.friends = []
        MiraiFactory.instance = self
        ChatMgr.slave_channel = channel

        self.loop.set_exception_handler(self.handle_exception)
        self.loop.run_until_complete(self.bot.handshake())

        @self.updater.add_handler([Event.Message])
        async def message_handler(event: Event.BaseEvent):
            try:
                if isinstance(event, Event.Message):
                    if event.type == MessageType.GROUP.value:
                        chat = ChatMgr.build_efb_chat_as_group(EFBGroupChat(
                            uid=f"group_{event.member.group.id}",
                            name=event.member.group.name
                        ))
                        author = ChatMgr.build_efb_chat_as_member(chat, EFBGroupMember(
                            name=event.member.memberName,
                            alias=await self.async_get_friend_remark(event.member.id),
                            uid=f'member_{event.member.id}'
                        ))
                    elif event.type == MessageType.FRIEND.value:
                        chat = ChatMgr.build_efb_chat_as_private(EFBPrivateChat(
                            uid=f'friend_{event.friend.id}',
                            name=event.friend.nickname,
                            alias=event.friend.remark
                        ))
                        author = chat.other
                    else:  # temp message
                        chat = ChatMgr.build_efb_chat_as_private(EFBPrivateChat(
                            uid=f'private_{event.member.id}_{event.member.group.id}',
                            name=event.member.memberName
                        ))
                        author = chat.other

                    messages = []
                    try:
                        for message in event.messageChain[1:]:
                            func = getattr(MiraiMessageProcessor, f'mirai_{message.type}')
                            messages.extend(await func(message, event, chat))
                    except:
                        print_exc()
                    message_id = event.messageChain.get_source().id

                    text = ""
                    ats = {}
                    for idx, val in enumerate(messages):
                        flag = False
                        if val.substitutions:
                            flag = True
                            for indexes, substitution in val.substitutions.items():
                                original_begin, original_end = indexes
                                new_begin = original_begin + len(text)
                                new_end = original_end + len(text)
                                ats[new_begin, new_end] = substitution
                        if val.text:
                            flag = True
                            text += val.text
                        if flag:
                            continue
                        val.uid = chat.uid + f"_{message_id}_{idx}"
                        val.chat = chat
                        val.author = author
                        val.deliver_to = coordinator.master
                        coordinator.send_message(val)
                        if val.file:
                            val.file.close()

                    # Finally send the text messages
                    if text:
                        text_msg = efb_text_simple_wrapper(text, ats)
                        text_msg.uid = chat.uid + f"_{message_id}"
                        text_msg.chat = chat
                        text_msg.author = author
                        text_msg.deliver_to = coordinator.master
                        coordinator.send_message(text_msg)
                        if text_msg.file:
                            text_msg.file.close()
                return True
            except:
                print_exc()
                return False

        @self.updater.add_handler([Event.BotOfflineEventForce])
        async def bot_offline_force_handler(event: Event.BotOfflineEventForce):
            pass

        def run():
            nonlocal self
            asyncio.set_event_loop(self.loop)
            self.loop.create_task(self.updater.run_task())
            self.loop.run_forever()

        try:
            t = threading.Thread(target=run)
            t.daemon = True
            t.start()
            # self.loop.run_until_complete(self.updater.run_task(shutdown_hook=self.shutdown_hook.wait))
        except:
            print_exc()

    def login(self):
        pass

    def logout(self):
        pass

    def relogin(self):
        pass

    def send_message(self, msg: 'Message') -> 'Message':
        chat_info = msg.chat.uid.split('_')
        chat_type = chat_info[0]
        chat_uid = chat_info[1]
        messages = []
        if msg.edit:
            try:
                asyncio.run_coroutine_threadsafe(self.bot.recall(int(msg.uid)), self.loop)
            except:
                print_exc()
                raise EFBOperationNotSupported("Failed to recall the message!\n"
                                               "This message may have already expired.")
        logging.getLogger(__name__).debug(f"Target: {msg.target}")
        if msg.type in [MsgType.Text, MsgType.Link]:
            if isinstance(msg.target, Message):
                max_length = 50
                uin = msg.target.author.uid.split("_")[1]
                messages.append(At(target=int(uin), display="@"))
                tgt_text = process_quote_text(msg.target.text, max_length)
                msg.text = "%s\n\n%s" % (tgt_text, msg.text)
            messages.append(Plain(text=msg.text))

        elif msg.type in (MsgType.Image, MsgType.Sticker, MsgType.Animation):
            self.logger.info("[%s] Image/Sticker/Animation %s", msg.uid, msg.type)
            messages.append(Image(path=msg.file.name))
            if msg.text:
                messages.append(Plain(text=msg.text))
        else:
            raise EFBOperationNotSupported(f"Unsupported message type {msg.type}")
        return_message = self.mirai_send_messages(chat_type, chat_info, messages)
        self.logger.debug(return_message)
        msg.uid = return_message.messageId
        return msg

    def send_status(self, status: 'Status'):
        pass

    def receive_message(self):
        # Replaced by on_*
        pass

    def get_friends(self) -> List['Chat']:  # This function should be only called by non-async function
        if not self.info_list.get('friend', None):
            if self.loop.is_running():
                friend_future = asyncio.run_coroutine_threadsafe(self.bot.friends, self.bot.loop)
                self.info_list['friend'] = friend_future.result()
            else:
                self.info_list['friend'] = self.loop.run_until_complete(self.bot.friends)

        friends = []
        self.info_dict['friend'] = {}
        for friend in self.info_list.get('friend', []):
            friend_uin = friend.id
            friend_name = friend.nickname
            friend_remark = friend.remark
            new_friend = EFBPrivateChat(
                uid=f"friend_{friend_uin}",
                name=friend_name,
                alias=friend_remark
            )
            self.info_dict['friend'][int(friend_uin)] = MiraiFriend(friend)
            friends.append(ChatMgr.build_efb_chat_as_private(new_friend))
        return friends

    def get_groups(self) -> List['Chat']:  # This function should be only called by non-async function
        if not self.info_list.get('group', None):
            if self.loop.is_running():
                group_future = asyncio.run_coroutine_threadsafe(self.bot.groups, self.bot.loop)
                self.info_list['group'] = group_future.result()
            else:
                self.info_list['group'] = self.loop.run_until_complete(self.bot.groups)
        groups = []
        self.info_dict['group'] = {}
        for group in self.info_list.get('group', []):
            group_name = group.name
            group_id = group.id
            new_group = EFBGroupChat(
                uid=f"group_{group_id}",
                name=group_name
            )
            self.info_dict['group'][int(group_id)] = MiraiGroup(group)
            groups.append(ChatMgr.build_efb_chat_as_group(new_group))
        return groups

    def get_login_info(self) -> Dict[Any, Any]:
        pass

    def get_stranger_info(self, user_id):
        pass

    def get_group_info(self, group_id, no_cache=True):
        if no_cache or not self.info_dict.get('group', None):
            self.get_groups()
        return self.info_dict['group'].get(int(group_id), None)

    def get_chat_picture(self, chat: 'Chat') -> BinaryIO:
        chat_type = chat.uid.split('_')
        if chat_type[0] == 'private':
            private_uin = chat_type[1].split('_')[0]
            return download_user_avatar(private_uin)
        elif chat_type[0] == 'friend':
            return download_user_avatar(chat_type[1])
        elif chat_type[0] == 'group':
            return download_group_avatar(chat_type[1])

    def get_chat(self, chat_uid: ChatID) -> 'Chat':
        chat_info = chat_uid.split('_')
        chat_type = chat_info[0]
        chat_attr = chat_info[1]
        chat = None
        if chat_type == 'friend':
            chat_uin = int(chat_attr)
            if not self.info_list.get('friend', None) and chat_uin in self.info_list['friend']:
                chat = ChatMgr.build_efb_chat_as_private(EFBPrivateChat(
                    uid=f"friend_{chat_attr}",
                    name=self.info_list['friend'][chat_uin].remark,
                    alias=self.info_list['friend'][chat_uin].nickname
                ))
            else:
                remark_name = self.get_friend_remark(chat_uin)
                chat = ChatMgr.build_efb_chat_as_private(EFBPrivateChat(
                    uid=f"friend_{chat_attr}",
                    name=remark_name if remark_name else "",
                ))
        elif chat_type == 'group':
            chat_uin = int(chat_attr)
            group_info = self.get_group_info(chat_uin, no_cache=False)
            group_members = self.get_group_member_list(chat_uin, no_cache=False)
            chat = ChatMgr.build_efb_chat_as_group(EFBGroupChat(
                uid=f"group_{chat_uin}",
                name=group_info.get('name', "")
            ), group_members)
        elif chat_type == 'private':
            pass  # fixme
        elif chat_type == 'phone':
            pass  # fixme
        return chat

    def get_chats(self) -> Collection['Chat']:
        return self.get_friends() + self.get_groups()

    def get_group_member_list(self, group_id, no_cache=True) -> List[EFBGroupMember]:
        if no_cache \
                or not self.group_member_list.get(group_id, None):  # Key expired or not exists
            if self.loop.is_running():
                group_result = asyncio.run_coroutine_threadsafe(self.bot.get_members(int(group_id)), self.loop)
                group_members = group_result.result()
            else:
                group_members = asyncio.run(self.bot.get_members(int(group_id)))
            efb_group_members: List[EFBGroupMember] = []
            for qq_member in group_members:
                qq_member = MiraiMember(qq_member)
                efb_group_members.append(EFBGroupMember(
                    name=qq_member['memberName'],
                    alias=self.get_friend_remark(qq_member['id']),
                    uid=qq_member['id']
                ))
            self.group_member_list[group_id] = efb_group_members
        return self.group_member_list[group_id]

    async def async_get_group_member_list(self, group_id, no_cache=True) -> List[EFBGroupMember]:
        if no_cache \
                or not self.group_member_list.get(group_id, None):  # Key expired or not exists
            group_members = await self.bot.get_members(int(group_id))
            efb_group_members: List[EFBGroupMember] = []
            for qq_member in group_members:
                qq_member = MiraiMember(qq_member)
                efb_group_members.append(EFBGroupMember(
                    name=qq_member['memberName'],
                    alias=self.get_friend_remark(qq_member['id']),
                    uid=qq_member['id']
                ))
            self.group_member_list[group_id] = efb_group_members
        return self.group_member_list[group_id]

    def poll(self):
        # loop = asyncio.new_event_loop()
        # self.bot.loop = loop
        # self.updater.run()
        # self.loop.run_until_complete(self.bot.session.close())
        # self.loop = asyncio.new_event_loop()
        # asyncio.set_event_loop(self.loop)
        # self.bot = Bot(self.uin, self.client_config['host'], self.client_config['port'], self.authKey, self.loop)
        # self.updater = Updater(self.bot)
        # self.shutdown_hook = asyncio.Event()
        # self.loop.set_exception_handler(self.handle_exception)
        pass

    def stop_polling(self):
        # self.bot.session.close()
        # self.shutdown_hook.set()
        # self.loop.stop()
        pass

    async def async_update_friend(self):
        pass

    def get_friend_remark(self, uin: int) -> Union[None, str]:
        uin = int(uin)
        count = 0
        while count <= 1:
            if not self.info_list.get('friend', None):
                self.get_friends()
                count += 1
            else:
                break
        if count > 1:  # Failure or friend not found
            raise Exception("Failed to update friend list!")  # todo Optimize error handling
        if not self.info_dict.get('friend', None) or uin not in self.info_dict['friend']:
            return None
        return self.info_dict['friend'][uin].get('remark', None)

    async def async_get_friend_remark(self, uin: int) -> Union[None, str]:
        # logging.getLogger(__name__).info('async_get_friend_remark called')
        uin = int(uin)
        count = 0
        while count <= 1:
            if not self.info_list.get('friend', None):
                self.info_list['friend'] = await self.bot.friends
                count += 1
            else:
                break
        if count > 1:  # Failure or friend not found
            raise Exception("Failed to update friend list!")  # todo Optimize error handling
        # logging.getLogger(__name__).info('async_get_friend_remark returned')
        if not self.info_dict.get('friend', None) or uin not in self.info_dict['friend']:
            return None
        return self.info_dict['friend'][uin].get('remark', None)

    def handle_exception(self, loop, context):
        # context["message"] will always be there; but context["exception"] may not
        print_exc()
        msg = context.get("exception", context["message"])
        logging.getLogger(__name__).exception('Unhandled exception: ', exc_info=msg)
        logging.getLogger(__name__).exception(context)

    def mirai_send_messages(self, chat_type: str, chat_uid: List[str], messages: List[BaseMessageComponent]) -> BotMessage:
        temp_group = None
        if chat_type == 'friend':
            message_type = MessageType.FRIEND
            target = int(chat_uid[1])
        elif chat_type == 'group':
            message_type = MessageType.GROUP
            target = int(chat_uid[1])
        else:
            message_type = MessageType.TEMP
            chat_user_id = int(chat_uid[1])
            chat_origin = int(chat_uid[2])
            target = chat_user_id
            temp_group = chat_origin
        return asyncio.run_coroutine_threadsafe(self.bot.send_message(target=target,
                                                                      message_type=message_type,
                                                                      message=messages,
                                                                      temp_group=temp_group), self.loop).result()
