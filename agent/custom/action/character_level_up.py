import time
from difflib import SequenceMatcher

from maa.agent.agent_server import AgentServer
from maa.context import Context
from maa.custom_action import CustomAction
from maa.pipeline import JOCR, JRecognitionType
from utils import logger
from utils.maa_types import ocr_results
from utils.params import parse_params

# 角色名别名：用户输入 → 游戏内可能的显示名
_CHARACTER_ALIASES: dict[str, tuple[str, ...]] = {
    "37": ("37", "三七"),
    "远旅": ("远旅", "远方的旅人"),
}


def _resolve_target(target: str) -> list[str]:
    candidates = {target}
    candidates.update(_CHARACTER_ALIASES.get(target, ()))
    for alias, names in _CHARACTER_ALIASES.items():
        if target in names:
            candidates.add(alias)
            candidates.update(names)
    return list(candidates)


def _match_name(target: str, text: str, min_ratio: float = 0.6) -> bool:
    cleaned = text.replace(" ", "").strip()
    if not cleaned:
        return False
    if target in cleaned:
        return True
    if len(target) >= 3 and cleaned in target:
        return True
    if len(target) >= 2 and len(cleaned) >= 2:
        return SequenceMatcher(None, target, cleaned).ratio() >= min_ratio
    return False


@AgentServer.custom_action("CultivationFindChar")
class CultivationFindChar(CustomAction):
    """在角色列表中按名检索目标角色，找到则点击进入详情，未找到则下滑一行重试。"""

    _MAX_SCROLLS: int = 20
    _CHAR_LIST_ROI: tuple[int, int, int, int] = (109, 380, 1073, 200)
    _SCROLL_BEGIN: tuple[int, int] = (640, 400)
    _SCROLL_END: tuple[int, int] = (640, 200)

    def run(
        self,
        context: Context,
        argv: CustomAction.RunArg,
    ) -> CustomAction.RunResult:
        param = parse_params(argv.custom_action_param, "target_character")
        target: str = param["target_character"]
        if not target:
            logger.error("目标角色名为空")
            return CustomAction.RunResult(success=False)

        candidates = _resolve_target(target)
        logger.debug(f"目标角色候选名: {candidates}")

        for i in range(self._MAX_SCROLLS):
            img = context.tasker.controller.post_screencap().wait().get()

            detail = context.run_recognition_direct(
                JRecognitionType.OCR,
                JOCR(roi=self._CHAR_LIST_ROI),
                img,
            )
            for r in ocr_results(detail):
                if any(_match_name(c, r.text) for c in candidates):
                    box = r.box
                    if box is not None:
                        cx = box[0] + box[2] // 2
                        cy = box[1] + box[3] // 2
                        context.tasker.controller.post_click(cx, cy).wait()
                        time.sleep(1)
                        logger.info(f"找到角色「{target}」，已点击")
                        return CustomAction.RunResult(success=True)

            logger.debug(f"第 {i + 1} 屏未找到「{target}」，下滑重试")
            context.tasker.controller.post_swipe(
                self._SCROLL_BEGIN[0],
                self._SCROLL_BEGIN[1],
                self._SCROLL_END[0],
                self._SCROLL_END[1],
                500,
            ).wait()
            time.sleep(1)

        logger.error(f"下滑 {self._MAX_SCROLLS} 次仍未找到角色「{target}」")
        return CustomAction.RunResult(success=False)
