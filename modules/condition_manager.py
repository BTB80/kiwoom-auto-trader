class ConditionManager:
    def __init__(self, api, log_fn=None):
        self.api = api
        self.log = log_fn or print

    def load_condition_list(self):
        cond_list_str = self.api.ocx.dynamicCall("GetConditionNameList()")

        if not cond_list_str:
            self.log("⚠️ 조건식 없음 (로그인 필요 또는 조건식 미등록)")
            return []

        cond_list = []
        for item in cond_list_str.split(";"):
            if "^" in item:  # ← 수정됨
                index, name = item.split("^", 1)
                cond_list.append((int(index), name.strip()))

        self.log(f"✅ 조건식 {len(cond_list)}개 로드됨")  # ✅ 심플 로그
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
