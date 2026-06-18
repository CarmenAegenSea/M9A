import time

from maa.agent.agent_server import AgentServer
from maa.context import Context
from maa.custom_action import CustomAction
from maa.pipeline import JOCR, JRecognitionType
from utils import logger
from utils.maa_types import ocr_results
from utils.params import parse_params


@AgentServer.custom_action("CultivationFindChar")
class CultivationFindChar(CustomAction):
    """在角色列表中按名检索目标角色，找到则点击进入详情，未找到则下滑一行重试。"""

    _MAX_SCROLLS: int = 20
    _CHAR_LIST_ROI: tuple[int, int, int, int] = (50, 120, 1180, 480)
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

        for i in range(self._MAX_SCROLLS):
            img = context.tasker.controller.post_screencap().wait().get()
            detail = context.run_recognition_direct(
                JRecognitionType.OCR,
                JOCR(roi=self._CHAR_LIST_ROI, only_rec=True),
                img,
            )
            for r in ocr_results(detail):
                if target in r.text:
                    box = r.box
                    if box is not None:
                        cx = box.x + box.w // 2
                        cy = box.y + box.h // 2
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
