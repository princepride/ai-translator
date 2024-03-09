
class Model():
    def __init__(self, modelname, selected_lora_model, selected_gpu):
        pass
    def generate(self, inputs, original_language, target_languages, max_batch_size):
        """
            return sample:
            [
                [
                    {
                        "target_language":"English",
                        "generated_translation":"I love you",
                    },
                    {
                        "target_language":"Chinese",
                        "generated_translation":"我爱你",
                    },
                ],
                [
                    {
                        "target_language":"English",
                        "generated_translation":"Who's your daddy",
                    },
                    {
                        "target_language":"Chinese",
                        "generated_translation":"谁是你爸爸",
                    },
                ],
                [
                    {
                        "target_language":"English",
                        "generated_translation":"Today is Friday",
                    },
                    {
                        "target_language":"Chinese",
                        "generated_translation":"今天是星期五",
                    },
                ],
            ]
        """
        pass