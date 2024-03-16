class Attribute:
    def __init__(self, attribute_literal: str) -> None:
        self._attribute_literal = attribute_literal

    @property
    def has_key(self) -> bool:
        return hasattr(self, "_key_as_str")

    @property
    def attribute_literal(self) -> str:
        return self._attribute_literal

    @property
    def value(self) -> str:
        return self._value_as_str


class AttributeWithKey(Attribute):
    def __init__(
        self, attribute_literal: str, key_literal: str, value_literal: str
    ) -> None:
        super().__init__(attribute_literal)

        if value_literal[0] in ["'", '"'] and value_literal[0] == value_literal[-1]:
            self._value_as_str = value_literal[1:-1]
        else:
            self._value_as_str = value_literal

        self.key_literal=key_literal
        self._key_as_str = key_literal.lower()
        self.value_literal = value_literal

    @property
    def key(self) -> str:
        return self._key_as_str


class AttributeWithoutKey(Attribute):
    def __init__(self, attribute_literal: str) -> None:
        super().__init__(attribute_literal)
        if (
            attribute_literal[0] in ["'", '"']
            and attribute_literal[0] == attribute_literal[-1]
        ):
            self._value_as_str = attribute_literal[1:-1]
        else:
            self._value_as_str = attribute_literal

        self.value_literal = attribute_literal
