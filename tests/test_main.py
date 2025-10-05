from src.main import hello_world


def test_hello_world() -> None:
    result = hello_world()
    if result != "Hello, world!":
        raise AssertionError("Unexpected result: {}".format(result))
