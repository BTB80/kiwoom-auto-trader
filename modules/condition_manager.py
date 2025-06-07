class ConditionManager:
    def __init__(self, api, log_fn=None):
        self.api = api
        self.log = log_fn or print

    def load_condition_list(self):
        cond_list_str = self.api.ocx.dynamicCall("GetConditionNameList()")
        self.log(f"📥 [Raw 조건식 문자열] {cond_list_str}")

        if not cond_list_str:
            self.log("⚠️ 조건식 목록이 비어 있습니다. 조건식을 먼저 생성하거나 로그인 후 다시 시도하세요.")
            return []

        cond_list = []
        for item in cond_list_str.split(";"):
            if ":" in item:
                index, name = item.split(":", 1)
                cond_list.append((int(index), name.strip()))

        self.log(f"✅ [조건식 목록 파싱 완료] {cond_list}")
        return cond_list
    
    def request_condition(self, screen_no, condition_name, condition_index, real_time=True):
        flag = 1 if real_time else 0
        self.api.ocx.dynamicCall(
            "SendCondition(QString, QString, int, int)",
            screen_no, condition_name, condition_index, flag
        )
        self.log(f"🔍 조건식 실행 요청: {condition_name} (index: {condition_index}, 실시간: {flag})")

    def stop_condition(self, screen_no, condition_name, condition_index):
        self.api.ocx.dynamicCall(
            "SendConditionStop(QString, QString, int)",
            screen_no, condition_name, condition_index
        )
        self.log(f"🛑 조건식 중단: {condition_name} (index: {condition_index})")
