"""
End-to-end test of the @observe decorator.

Run with: python examples/test_observe.py
(Backend must be running on localhost:8000.)
"""
import asyncio
import time

from tracelite import init, observe, shutdown


# Initialize the SDK (starts the background sender)
init(api_key="local-dev-key", base_url="http://localhost:8000")


@observe(name="add_numbers")
def add(a: int, b: int) -> int:
    return a + b


@observe(name="slow_work", span_type="generic")
def slow_work(n: int) -> int:
    time.sleep(0.05)
    return n * n


@observe(name="async_work")
async def async_work(label: str) -> str:
    await asyncio.sleep(0.02)
    return f"done: {label}"


@observe(name="boom")
def boom():
    raise ValueError("intentional error for testing")


def main():
    print(">>> Calling sync functions...")
    print("add(2, 3) =", add(2, 3))
    print("slow_work(7) =", slow_work(7))

    print(">>> Calling async function...")
    print(asyncio.run(async_work("hello")))

    print(">>> Calling a failing function (we'll catch the error)...")
    try:
        boom()
    except ValueError as e:
        print(f"caught: {e}")

    print(">>> Generating 25 quick spans to exercise the batcher...")
    for i in range(25):
        add(i, i)

    print(">>> Shutting down — this flushes any pending spans.")
    shutdown()
    print(">>> Done.")


if __name__ == "__main__":
    main()