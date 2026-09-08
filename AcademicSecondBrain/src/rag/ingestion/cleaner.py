import re
from typing import List,Any
from llama_index.core.schema import TransformComponent, BaseNode

class ArtifactCleaner(TransformComponent):
    def __call__(self,nodes:List[BaseNode], *args, **kwargs) ->List[BaseNode]:
        for node in nodes:
            text = node.text
            text=self._cleanText(text)
            text=self._cleanWhitespaces(text)
            node.set_content(text)
        return nodes

    def _cleanText(self,text:str):
        text=re.sub(r'(\w)-\n(\w)', r'\1\2', text)
        text=re.sub(r'--- Page \d+ ---\n?', '', text)
        text=re.sub(r'([a-z])([A-Z][a-z])', r'\1 \2', text)
        merged_words={
            'anda': 'and a',
            'ofthe': 'of the',
            'inthe': 'in the',
            'forthe': 'for the',
            'tothe': 'to the',
            'onthe': 'on the',
            'withthe': 'with the',
            'bythe': 'by the',
            'fromthe': 'from the'
        }
        for merged,correct in merged_words.items():
            text=re.sub(r'\b' + merged + r'\b', correct, text, flags=re.IGNORECASE)
        text = re.sub(r'[ \t]+', ' ', text)
        text = text.strip()
        return text
    def _cleanWhitespaces(self,text:str):
        text = re.sub(r'[ \t]+', ' ', text)
        text = re.sub(r'\n{3,}', '\n\n', text)
        lines = text.split('\n')
        cleaned_lines = [line.strip() for line in lines]
        result_lines = []
        prev_empty = False
        for line in cleaned_lines:
            if line:
                result_lines.append(line)
                prev_empty = False
            elif not prev_empty:
                result_lines.append('')
                prev_empty = True

        return '\n'.join(result_lines)