"""Richer mock data for frontend testing: characters with many nested state fields, and chats already
some rounds in, with state changes of every kind and illustrations in every finished status.

Used by mock_backend.py. Each story is added once, by character name, so an existing mock database
gains the ones it lacks on the next start.
"""

import copy
import uuid
from typing import Any, Callable

STATE_BASE = '''
from pydantic import BaseModel, ConfigDict, Field


class StateNode(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_default=True)


def bar(default: int, top: int = 100):
    return Field(default, json_schema_extra={"display": "bar", "max": top})
'''

SHEN_SCHEMA = STATE_BASE + '''

class WorldState(StateNode):
    日期: str = "2026-10-19"
    星期: str = "星期一"
    时间: str = "21:30"
    地点: str = "城北旧图书馆"
    天气: str = "小雨"
    氛围: str = "安静"


class Appearance(StateNode):
    发色: str = "黑"
    衣着: str = "灰色毛衣"
    特征: list[str] = Field(default_factory=lambda: ["左手戴着旧手表"])


class Condition(StateNode):
    体力: int = bar(80)
    伤势: str = "无"


class CharacterState(StateNode):
    好感度: int = bar(10)
    信任: int = bar(5)
    关系: str = "陌生"
    心情: str = "警惕"
    想法: str = ""
    外貌: Appearance = Field(default_factory=Appearance)
    身体: Condition = Field(default_factory=Condition)
    已知线索: list[str] = Field(default_factory=list)
    秘密: list[str] = Field(default_factory=lambda: ["知道地下书库的钥匙在哪"], json_schema_extra={"display": "hidden"})


class Items(StateNode):
    背包: list[str] = Field(default_factory=lambda: ["旧地图"])
    金钱: int = 20


class MainQuest(StateNode):
    名称: str = "寻找缺页"
    阶段: str = "起点"
    进度: int = bar(0)


class SideQuest(StateNode):
    名称: str
    状态: str = "进行中"


class Quests(StateNode):
    主线: MainQuest = Field(default_factory=MainQuest)
    支线: list[SideQuest] = Field(default_factory=list)


class Schema(StateNode):
    世界: WorldState = Field(default_factory=WorldState)
    角色: CharacterState = Field(default_factory=CharacterState)
    物品: Items = Field(default_factory=Items)
    任务: Quests = Field(default_factory=Quests)
'''

ENSEMBLE_SCHEMA = STATE_BASE + '''

class WorldState(StateNode):
    日期: str = "2026-03-02"
    星期: str = "星期一"
    时间: str = "06:40"
    地点: str = "雾港码头"
    天气: str = "浓雾"


class Person(StateNode):
    好感度: int = bar(30)
    关系: str = "同伴"
    心情: str = "平静"
    位置: str = "码头"
    状态: list[str] = Field(default_factory=list)


class Team(StateNode):
    士气: int = bar(60)
    补给: int = 12
    成员: list[str] = Field(default_factory=lambda: ["林晚", "苏念", "你"])
    目标: str = "在天亮前登上去北岛的船"


class Schema(StateNode):
    世界: WorldState = Field(default_factory=WorldState)
    林晚: Person = Field(default_factory=Person)
    苏念: Person = Field(default_factory=lambda: Person(好感度=15, 关系="旧识", 心情="戒备"))
    队伍: Team = Field(default_factory=Team)
'''

# Each round: (user input, AI text, state changes merged into the previous state, illustration or None).
# An illustration is (width, height, status, hidden); a failed one shows the mock ComfyUI error.
Round = tuple[str, str, dict[str, Any], tuple[int, int, str, bool] | None]

SHEN_ROUNDS: list[Round] = [
    ("我抱着地图走到他的桌前：“打扰一下，你知道这张地图上缺的那一页在哪吗？”",
     "他没有立刻抬头，指尖在泛黄的书页上停了一会儿，才慢慢合上书。\n\n"
     "“这里九点半就闭馆了。”他的声音很低，像是怕惊动了书架上的灰尘，“不过，你要找的东西，大概不在地图上。”\n\n"
     "窗外的雨声忽然大了。他看了一眼你怀里的地图，目光在右下角那个被撕掉的缺口上停了很久。",
     {"世界": {"时间": "21:40", "氛围": "压抑"}, "角色": {"好感度": 15, "心情": "好奇", "想法": "她怎么会有这张图"},
      "任务": {"主线": {"阶段": "初遇", "进度": 10}}},
     (1344, 768, "ready", False)),
    ("“那它在哪儿？”我把地图摊在他桌上。",
     "他终于抬起眼。台灯从下方照上来，把他的轮廓切成明暗两半。\n\n"
     "“在你明天之前，不该看到的那一页里。”他伸手把地图转了个方向，指着一处被水渍晕开的标记，“这里，原本是地下书库的入口。三十年前就封了。”\n\n"
     "他说完便站起身，从抽屉里取出一盏手提灯，又顿了顿，像是在犹豫要不要把它递给你。",
     {"世界": {"时间": "21:55"}, "角色": {"好感度": 22, "信任": 12, "已知线索": ["地下书库入口"], "想法": "也许可以信她一次"},
      "物品": {"背包": ["旧地图", "手提灯"]}, "任务": {"主线": {"阶段": "地下书库", "进度": 25}}},
     (832, 1216, "ready", False)),
    ("我接过手提灯：“你陪我下去吗？”",
     "“我值夜班。”他说，“夜班的人不该离开前台。”\n\n"
     "可他还是拿起了外套。经过借阅台时，他把一枚铜钥匙放进口袋，动作快得像是不想让你看见。\n\n"
     "楼梯尽头的铁门上挂着一把生锈的锁。他蹲下来，借着灯光看了很久，然后低声说：“有人在我们之前来过。”",
     {"世界": {"时间": "22:20", "地点": "地下书库入口", "氛围": "紧张"},
      "角色": {"信任": 20, "心情": "紧张", "外貌": {"衣着": "深色旧呢大衣"}, "已知线索": ["地下书库入口", "锁上有新划痕"]},
      "任务": {"支线": [{"名称": "查明先来的人", "状态": "进行中"}]}},
     None),
    ("我凑近去看锁上的划痕。",
     "划痕很新，铁锈下露出的金属还闪着光。他用指腹擦过，皱起眉。\n\n"
     "“三天前我来巡查的时候还没有。”他从口袋里拿出那枚铜钥匙，在你面前晃了晃，“这把锁，只有两把钥匙。”\n\n"
     "门开的一瞬间，一股潮湿的纸张气味涌了出来。黑暗里，有什么东西从高处的书架上掉了下来，啪的一声落在你脚边——是一本没有封面的书。",
     {"世界": {"时间": "22:35", "地点": "地下书库"}, "角色": {"好感度": 28, "信任": 30, "关系": "同伴"},
      "物品": {"背包": ["旧地图", "手提灯", "无封面的书"]}, "任务": {"主线": {"阶段": "无封面的书", "进度": 45}}},
     (1344, 768, "ready", False)),
    ("我捡起那本书，翻到最后一页。",
     "最后一页被整齐地裁掉了，裁口和你地图上的缺口一模一样。\n\n"
     "他接过书，借着灯光看了很久，忽然笑了一下，那是你第一次见他笑。“原来是这样。地图不是地图，是这本书的书签。”\n\n"
     "可他的笑很快就收住了。楼梯上传来脚步声，很轻，却一步一步往下走。他把灯熄了，拉着你躲进两排书架之间。",
     {"世界": {"时间": "22:50", "氛围": "危险"}, "角色": {"好感度": 36, "心情": "专注", "想法": "得先把她藏好",
                                                        "已知线索": ["地下书库入口", "锁上有新划痕", "书与地图同一裁口"]},
      "任务": {"主线": {"进度": 60}}},
     (1344, 768, "failed", False)),
    ("黑暗里，我屏住呼吸，悄悄握住了他的手。",
     "他的手很凉，指节僵了一下，却没有抽开。\n\n"
     "脚步声在你们藏身的书架前停住了。手电的光扫过地面，扫过那本你们来不及收起的书，又慢慢移开。\n\n"
     "等脚步声远去，他才低声开口，声音近得几乎贴着你的耳朵：“是馆长。他不该知道这里还开着。”",
     {"世界": {"时间": "23:05"}, "角色": {"好感度": 48, "信任": 42, "心情": "动摇", "身体": {"体力": 65}},
      "任务": {"支线": [{"名称": "查明先来的人", "状态": "已完成"}, {"名称": "避开馆长", "状态": "进行中"}]}},
     (832, 1216, "ready", True)),
    ("“我们得离开这里。”我小声说。",
     "回到地面时，雨已经停了。他把那本书塞进你的包里，又把自己的外套披在你肩上。\n\n"
     "“明天中午，城北书店。”他说，“老板会把缺页交给你。别告诉任何人是我让你去的。”\n\n"
     "你还想再问什么，他已经转身回到借阅台后面，重新打开台灯，像什么也没发生过一样，继续翻那本没看完的书。",
     {"世界": {"日期": "2026-10-20", "星期": "星期二", "时间": "00:10", "地点": "城北旧图书馆", "天气": "雨停", "氛围": "安静"},
      "角色": {"关系": "盟友", "心情": "不舍", "想法": "希望她明天平安", "身体": {"伤势": "手背擦伤"}},
      "物品": {"背包": ["旧地图", "手提灯", "无封面的书", "他的外套"], "金钱": 12},
      "任务": {"主线": {"阶段": "城北书店", "进度": 75}}},
     None),
    ("第二天中午，我来到城北书店。",
     "书店的门铃叮当一响。柜台后坐着的，竟然是他。\n\n"
     "“老板今天休息。”他把一个牛皮纸信封推到你面前，耳根有一点红，“我想了想，还是我自己交给你比较放心。”\n\n"
     "信封里是那一页缺页。纸上画着一扇门，门旁写着一行小字：给能把书带回来的人。",
     {"世界": {"时间": "12:05", "地点": "城北书店", "天气": "晴", "氛围": "温暖"},
      "角色": {"好感度": 62, "信任": 58, "心情": "害羞", "想法": "", "外貌": {"衣着": "白衬衫", "特征": ["左手戴着旧手表", "耳根发红"]},
             "已知线索": ["地下书库入口", "锁上有新划痕", "书与地图同一裁口", "缺页上的门"]},
      "物品": {"背包": ["旧地图", "无封面的书", "他的外套", "缺页"]},
      "任务": {"主线": {"阶段": "缺页上的门", "进度": 90}, "支线": [{"名称": "查明先来的人", "状态": "已完成"}]}},
     (1344, 768, "ready", False)),
]

ENSEMBLE_ROUNDS: list[Round] = [
    ("我拉紧外套：“船几点开？”",
     "“七点整。”林晚看了一眼怀表，又抬头望向雾里，“如果它还会来的话。”\n\n"
     "苏念靠在木桩上，没有接话。她的目光一直落在码头尽头那盏忽明忽暗的灯上。",
     {"世界": {"时间": "06:50"}, "林晚": {"心情": "焦虑"}, "苏念": {"状态": ["警觉"]}},
     None),
    ("“那盏灯怎么了？”我问苏念。",
     "“有人在打信号。”苏念终于开口，“三短一长。是走私船的暗号。”\n\n"
     "林晚皱眉：“你怎么知道？”\n\n"
     "苏念没有回答，只是把围巾往上拉了拉，遮住了半张脸。",
     {"世界": {"时间": "06:58"}, "苏念": {"好感度": 20, "心情": "回避", "状态": ["警觉", "有所隐瞒"]},
      "林晚": {"关系": "同伴", "状态": ["怀疑苏念"]}, "队伍": {"士气": 52}},
     None),
    ("我挡在两人中间：“先上船，别的上去再说。”",
     "汽笛声从雾里传来。一艘没有挂旗的小船慢慢靠岸，船头站着一个戴斗笠的人。\n\n"
     "“三个人？”那人数了数，“说好是两个。”\n\n"
     "林晚往前一步，把一袋东西扔了过去：“多的这份，够你开到北岛了。”",
     {"世界": {"时间": "07:02", "地点": "无名船"}, "林晚": {"好感度": 38, "心情": "果断", "位置": "船头"},
      "苏念": {"位置": "船尾"}, "队伍": {"补给": 8, "士气": 58}},
     None),
    ("船开出不久，我去船尾找苏念。",
     "她坐在缆绳堆上，正把一枚铜徽章在指间翻来翻去。看见你，她没有藏。\n\n"
     "“我以前在走私船上待过两年。”她说，“林晚不知道。我也不想她知道。”\n\n"
     "雾散了一点，远处露出一线灰白的海岸。",
     {"世界": {"时间": "08:30", "天气": "雾散"}, "苏念": {"好感度": 34, "关系": "信任的同伴", "心情": "释然", "状态": ["有所隐瞒"]},
      "队伍": {"士气": 64}},
     None),
    ("回到船头时，林晚递给我一块干粮。",
     "“她跟你说了？”林晚没看你，只是盯着海面，“我早就猜到了。在码头她看灯的样子，像在等老朋友。”\n\n"
     "她把剩下的干粮分成三份：“到了北岛，我们需要她。这件事，我们谁也别提。”",
     {"世界": {"时间": "09:10"}, "林晚": {"好感度": 45, "心情": "平静", "状态": []}, "队伍": {"补给": 5}},
     None),
    ("北岛的码头出现在视线里。",
     "码头上站着一排穿制服的人。斗笠男人骂了一句，猛地转舵。\n\n"
     "“抓紧！”苏念喊道。小船擦着礁石冲进一条窄窄的水道，船身剧烈地摇晃。林晚一把拉住你，三个人一起滚进了船舱。\n\n"
     "等船终于停下，四周只剩下海浪拍打岩洞的回声。",
     {"世界": {"日期": "2026-03-02", "时间": "10:25", "地点": "北岛岩洞", "天气": "阴"},
      "林晚": {"状态": ["擦伤"], "位置": "船舱"}, "苏念": {"位置": "船舱", "心情": "兴奋"},
      "队伍": {"士气": 70, "成员": ["林晚", "苏念", "你", "斗笠船夫"], "目标": "从岩洞找到上岛的路"}},
     None),
]


def merge(state: dict, change: dict) -> dict:
    """The next state: nested objects merge, everything else (lists included) is replaced."""
    out = copy.deepcopy(state)
    for key, value in change.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = merge(out[key], value)
        else:
            out[key] = copy.deepcopy(value)
    return out


STORIES = [
    {
        "character": {
            "name": "沈砚", "description": "城北旧图书馆的夜班管理员，沉默寡言，记得每一本书放在哪里，也记得每一个不该在闭馆后出现的人。",
            "scenes": [{"name": "闭馆后", "description": "雨夜，图书馆只剩一盏台灯",
                        "first_message": "<content>灯一盏盏熄灭。\n\n闭馆铃响过第三遍，长廊尽头只剩一盏铜罩台灯还亮着。"
                                         "你抱着借来的旧地图站在书架之间，听见身后有人合上了书。</content>"}],
            "state_schema": SHEN_SCHEMA,
            "definitions": [{"content": "沈砚是图书馆的夜班管理员，话少，心细，对馆里的秘密知道得比他说的多。"}],
        },
        "title": "沈砚 · 缺页", "rounds": SHEN_ROUNDS,
    },
    {
        "character": {
            "name": "林晚与苏念", "description": "两个结伴逃离雾港的女人：林晚冷静果断，苏念沉默而藏着过去。用于测试多个角色同时出现的状态。",
            "scenes": [{"name": "雾港", "description": "天亮前的码头",
                        "first_message": "<content>雾从海面漫上来，把码头的灯吞得只剩一圈模糊的光。林晚站在你左边，苏念站在你右边，谁也没有说话。</content>"}],
            "state_schema": ENSEMBLE_SCHEMA,
            "definitions": [{"content": "林晚和苏念是旅途中的同伴，彼此之间有未说出口的事。"}],
        },
        "title": "雾港 · 北岛", "rounds": ENSEMBLE_ROUNDS,
    },
]


def seed_stories(client, database, images_root, png: Callable[[int, int, int], bytes]) -> list[str]:
    """Adds each story whose character is missing; returns the names added."""
    from backend.illustrations.models import Illustration
    from backend.repository.archive import ArchiveRepository

    existing = {c["name"] for c in client.get("/api/characters").json()}
    identity = next(iter(client.get("/api/user-identities").json()), None)
    presets = client.get("/api/writing-presets").json()
    models = client.get("/api/model-configs").json()
    workflows = client.get("/api/image-workflows").json()
    added = []
    for story in STORIES:
        if story["character"]["name"] in existing or identity is None:
            continue
        character = client.post("/api/characters", json=story["character"])
        character.raise_for_status()
        body = {"title": story["title"], "character_id": character.json()["id"], "user_identity_id": identity["id"]}
        if presets:
            body |= {"writing_preset_ids": [presets[0]["id"]], "writing_preset_id": presets[0]["id"]}
        if models:
            body |= {"model_config_ids": [models[0]["id"]],
                     "model_bindings": {p: models[0]["id"] for p in ("writing", "state_update", "round_summary", "episode_summary")}}
        chat = client.post("/api/chats", json=body)
        chat.raise_for_status()
        chat_id = chat.json()["id"]
        state = chat.json()["latest_state"]["content"]
        if workflows and any(r[3] for r in story["rounds"]):
            imported = client.post(f"/api/chats/{chat_id}/image-workflows/import", json={"source_id": workflows[0]["id"]})
            imported.raise_for_status()
            client.put(f"/api/chats/{chat_id}/illustration-settings",
                       json={"mode": "manual", "image_workflow_id": imported.json()["id"]}).raise_for_status()
        for number, (user_input, text, change, picture) in enumerate(story["rounds"], 1):
            state = merge(state, change)
            with database.transaction() as session:
                repo = ArchiveRepository(session)
                record = repo.create_round(chat_id, user_input, f"<content>{text}</content>")
                repo.save_state(record.id, copy.deepcopy(state))
                repo.save_summary(record.id, text.split("\n\n")[0][:60])
                repo.save_decision(record.id)
                if picture:
                    width, height, status, hidden = picture
                    item = Illustration(id=str(uuid.uuid4()), chat_id=chat_id, round_id=record.id, status=status, seed=number * 97,
                                        prompt={"prompt": f"mock scene {number}"}, width=width, height=height, hidden=hidden)
                    if status == "failed":
                        item.error = "ComfyUI 拒绝了工作流：ckpt_name 'mock.safetensors' 不在列表中"
                    if status == "ready":
                        folder = images_root / chat_id
                        folder.mkdir(parents=True, exist_ok=True)
                        scale = 480 / max(width, height)
                        (folder / f"{item.id}.png").write_bytes(png(round(width * scale), round(height * scale), item.seed))
                        item.file_name, item.media_type = f"{chat_id}/{item.id}.png", "image/png"
                    session.add(item)
        added.append(story["character"]["name"])
    return added
