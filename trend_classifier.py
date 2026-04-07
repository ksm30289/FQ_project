class TrendClassifier:
    def __init__(self, sheet_client):
        self.sheet_client = sheet_client

    def split_by_category(self, rows):
        positive = []
        negative = []
        suggestion = []

        for r in rows:
            c = r.get("category")

            row = [
                r["datetime"],
                r["user"],
                r["message"],
            ]

            if c == "positive":
                positive.append(row)
            elif c == "negative":
                negative.append(row)
            elif c == "suggestion":
                suggestion.append(row)

        return positive, negative, suggestion

    def upload(self, positive, negative, suggestion):
        if positive:
            self.sheet_client.append_to_sheet("긍정", positive)
        if negative:
            self.sheet_client.append_to_sheet("부정", negative)
        if suggestion:
            self.sheet_client.append_to_sheet("건의", suggestion)
