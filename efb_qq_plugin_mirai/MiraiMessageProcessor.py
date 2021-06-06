import asyncio
import logging

from ehforwarderbot import Chat
from mirai_core.models.Event import Message
from mirai_core.models.Message import Plain, Image, Quote, Face, At, FlashImage, AtAll, Xml, Json, Poke, App
from mirai_core.models.Types import MessageType

from efb_qq_plugin_mirai.MiraiConfig import MiraiConfig
from efb_qq_plugin_mirai.MiraiFactory import MiraiFactory
from efb_qq_plugin_mirai.MsgDecorator import efb_text_simple_wrapper, efb_image_wrapper, efb_unsupported_wrapper
from efb_qq_plugin_mirai.Utils import download_file, async_download_file

logger = logging.getLogger(__name__)

qq_emoji_list = {  # created by JogleLew and jqqqqqqqqqq, optimized based on Tim's emoji support
    0:   '😮',
    1:   '😣',
    2:   '😍',
    3:   '😳',
    4:   '😎',
    5:   '😭',
    6:   '☺️',
    7:   '😷',
    8:   '😴',
    9:   '😭',
    10:  '😰',
    11:  '😡',
    12:  '😝',
    13:  '😃',
    14:  '🙂',
    15:  '🙁',
    16:  '🤓',
    17:  '[Empty]',
    18:  '😤',
    19:  '😨',
    20:  '😏',
    21:  '😊',
    22:  '🙄',
    23:  '😕',
    24:  '🤤',
    25:  '😪',
    26:  '😨',
    27:  '😓',
    28:  '😬',
    29:  '🤑',
    30:  '✊',
    31:  '😤',
    32:  '🤔',
    33:  '🤐',
    34:  '😵',
    35:  '😩',
    36:  '💣',
    37:  '💀',
    38:  '🔨',
    39:  '👋',
    40:  '[Empty]',
    41:  '😮',
    42:  '💑',
    43:  '🕺',
    44:  '[Empty]',
    45:  '[Empty]',
    46:  '🐷',
    47:  '[Empty]',
    48:  '[Empty]',
    49:  '🤷',
    50:  '[Empty]',
    51:  '[Empty]',
    52:  '[Empty]',
    53:  '🎂',
    54:  '⚡',
    55:  '💣',
    56:  '🔪',
    57:  '⚽️',
    58:  '[Empty]',
    59:  '💩',
    60:  '☕️',
    61:  '🍚',
    62:  '[Empty]',
    63:  '🌹',
    64:  '🥀',
    65:  '[Empty]',
    66:  '❤️',
    67:  '💔️',
    68:  '[Empty]',
    69:  '🎁',
    70:  '[Empty]',
    71:  '[Empty]',
    72:  '[Empty]',
    73:  '[Empty]',
    74:  '🌞️',
    75:  '🌃',
    76:  '👍',
    77:  '👎',
    78:  '🤝',
    79:  '✌️',
    80:  '[Empty]',
    81:  '[Empty]',
    82:  '[Empty]',
    83:  '[Empty]',
    84:  '[Empty]',
    85:  '🥰',
    86:  '[怄火]',
    87:  '[Empty]',
    88:  '[Empty]',
    89:  '🍉',
    90:  '[Empty]',
    91:  '[Empty]',
    92:  '[Empty]',
    93:  '[Empty]',
    94:  '[Empty]',
    95:  '[Empty]',
    96:  '😅',
    97:  '[擦汗]',
    98:  '[抠鼻]',
    99:  '👏',
    100: '[糗大了]',
    101: '😏',
    102: '😏',
    103: '😏',
    104: '🥱',
    105: '[鄙视]',
    106: '😭',
    107: '😭',
    108: '[阴险]',
    109: '😚',
    110: '🙀',
    111: '[可怜]',
    112: '🔪',
    113: '🍺',
    114: '🏀',
    115: '🏓',
    116: '❤️',
    117: '🐞',
    118: '[抱拳]',
    119: '[勾引]',
    120: '✊',
    121: '[差劲]',
    122: '🤟',
    123: '🚫',
    124: '👌',
    125: '[转圈]',
    126: '[磕头]',
    127: '[回头]',
    128: '[跳绳]',
    129: '👋',
    130: '[激动]',
    131: '[街舞]',
    132: '😘',
    133: '[左太极]',
    134: '[右太极]',
    135: '[Empty]',
    136: '[双喜]',
    137: '🧨',
    138: '🏮',
    139: '💰',
    140: '[K歌]',
    141: '🛍️',
    142: '📧',
    143: '[帅]',
    144: '👏',
    145: '🙏',
    146: '[爆筋]',
    147: '🍭',
    148: '🍼',
    149: '[下面]',
    150: '🍌',
    151: '🛩',
    152: '🚗',
    153: '🚅',
    154: '[车厢]',
    155: '[高铁右车头]',
    156: '🌥',
    157: '下雨',
    158: '💵',
    159: '🐼',
    160: '💡',
    161: '[风车]',
    162: '⏰',
    163: '🌂',
    164: '[彩球]',
    165: '💍',
    166: '🛋',
    167: '[纸巾]',
    168: '💊',
    169: '🔫',
    170: '🐸',
    171: '🍵',
    172: '[眨眼睛]',
    173: '😭',
    174: '[无奈]',
    175: '[卖萌]',
    176: '[小纠结]',
    177: '[喷血]',
    178: '[斜眼笑]',
    179: '[doge]',
    180: '[惊喜]',
    181: '[骚扰]',
    182: '😹',
    183: '[我最美]',
    184: '🦀',
    185: '[羊驼]',
    186: '[Empty]',
    187: '👻',
    188: '🥚',
    189: '[Empty]',
    190: '🌼',
    191: '[Empty]',
    192: '🧧',
    193: '😄',
    194: '😞',
    195: '[Empty]',
    196: '[Empty]',
    197: '[冷漠]',
    198: '[呃]',
    199: '👍',
    200: '👋',
    201: '👍',
    202: '[无聊]',
    203: '[托脸]',
    204: '[吃]',
    205: '💐',
    206: '😨',
    207: '[花痴]',
    208: '[小样儿]',
    209: '[Empty]',
    210: '😭',
    211: '[我不看]',
    212: '[托腮]',
    213: '[Empty]',
    214: '😙',
    215: '[糊脸]',
    216: '[拍头]',
    217: '[扯一扯]',
    218: '[舔一舔]',
    219: '[蹭一蹭]',
    220: '[拽炸天]',
    221: '[顶呱呱]',
    222: '🤗',
    223: '[暴击]',
    224: '🔫',
    225: '[撩一撩]',
    226: '[拍桌]',
    227: '👏',
    228: '[恭喜]',
    229: '🍻',
    230: '[嘲讽]',
    231: '[哼]',
    232: '[佛系]',
    233: '[掐一掐]',
    234: '😮',
    235: '[颤抖]',
    236: '[啃头]',
    237: '[偷看]',
    238: '[扇脸]',
    239: '[原谅]',
    240: '[喷脸]',
    241: '🎂',
    242: '[Empty]',
    243: '[Empty]',
    244: '[Empty]',
    245: '[Empty]',
    246: '[Empty]',
    247: '[Empty]',
    248: '[Empty]',
    249: '[Empty]',
    250: '[Empty]',
    251: '[Empty]',
    252: '[Empty]',
    253: '[Empty]',
    254: '[Empty]',
    255: '[Empty]',
}


class MiraiMessageProcessor:
    @staticmethod
    async def mirai_Plain(ctx: Plain, event: Message, chat: Chat):
        if not ctx.text:
            return []
        content = ctx.text
        return [efb_text_simple_wrapper(content)]

    @staticmethod
    async def mirai_Image(ctx: Image, event: Message, chat: Chat):
        logging.getLogger(__name__).info("Start downloading image!")
        try:
            f = await async_download_file(ctx.url)
        except Exception as e:
            logger.warning(f"Failed to download the image! {e}")
        else:
            return [efb_image_wrapper(f)]

    @staticmethod
    async def mirai_Quote(ctx: Quote, event: Message, chat: Chat):
        original_message = ""
        for message in ctx.origin:
            if isinstance(message, Plain):
                original_message += message.text
            elif isinstance(message, Image):
                original_message += " [Image] "
            elif isinstance(message, Face):
                original_message += f" [Face {message.faceId}]"
        return [efb_text_simple_wrapper(f"「{original_message}」\n\n")]

    @staticmethod
    async def mirai_At(ctx: At, event: Message, chat: Chat):
        at_list = None
        if not ctx.display:
            if event.type == MessageType.GROUP.value:
                members = await MiraiFactory.instance.async_get_group_member_list(group_id=event.member.group.id,
                                                                                  no_cache=False)
                flag = False
                for member in members:
                    if int(member['uid']) == int(ctx.target):
                        ctx.display = f"@{member['name']}"
                        flag = True
                        break
                if not flag:
                    ctx.display = "@Unknown"
        if MiraiConfig.configs.get('qq', 0) == ctx.target:
            ctx.display = "@me"
            begin_index = 0
            end_index = len(ctx.display)
            at_list = {(begin_index, end_index): chat.self}
        logger.debug(at_list)
        return [efb_text_simple_wrapper(ctx.display, at_list)]

    @staticmethod
    async def mirai_Face(ctx: Face, event: Message, chat: Chat):
        qq_face = int(ctx.faceId) & 255
        if qq_face in qq_emoji_list:
            return [efb_text_simple_wrapper(qq_emoji_list[qq_face])]
        else:
            return [efb_text_simple_wrapper(f"[Face {ctx.faceId}]")]

    @staticmethod
    async def mirai_FlashImage(ctx: FlashImage, event: Message, chat: Chat):
        logging.getLogger(__name__).info("Start downloading image!")
        try:
            f = await async_download_file(ctx.url)
        except Exception as e:
            logger.warning(f"Failed to download the image! {e}")
        else:
            return [efb_image_wrapper(f)]

    @staticmethod
    async def mirai_AtAll(ctx: AtAll, event: Message, chat: Chat):
        content = "@all"
        begin_index = 0
        end_index = len(content)
        at_list = {(begin_index, end_index): chat.self}
        return [efb_text_simple_wrapper(content, at_list)]

    @staticmethod
    async def mirai_Xml(ctx: Xml, event: Message, chat: Chat):
        content = f"[XML]\n{ctx.xml}" if ctx.xml else "[Content missing]"
        return [efb_unsupported_wrapper(content)]

    @staticmethod
    async def mirai_Json(ctx: Json, event: Message, chat: Chat):
        content = f"[Json]\n{ctx.json}" if ctx.json else "[Content missing]"
        return [efb_unsupported_wrapper(content)]

    @staticmethod
    async def mirai_App(ctx: App, event: Message, chat: Chat):
        content = f"[App]\n{ctx.content}" if ctx.content else "[Content missing]"
        return [efb_unsupported_wrapper(content)]

    @staticmethod
    async def mirai_Poke(ctx: Poke, event: Message, chat: Chat):
        content = f"[Poke]\n{ctx.name}" if ctx.name else "[Content missing]"
        at_str = "@me"
        begin_index = len(content)
        end_index = begin_index + len(at_str)
        at_list = {(begin_index, end_index): chat.self}
        return [efb_text_simple_wrapper(content, at_list)]
