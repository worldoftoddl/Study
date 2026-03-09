from Agent.graph import react_agent


def main():
    thread_id = "cli-session-1"
    config = {"configurable": {"thread_id": thread_id}}

    print("=== ReAct Agent ===")
    print("도구: 웹 검색, 계산기, 스킬")
    print("종료: 'quit' 또는 'q' 입력\n")

    while True:
        user_input = input("사용자: ").strip()
        if not user_input:
            continue
        if user_input.lower() in ("quit", "q", "exit"):
            print("대화를 종료합니다.")
            break

        result = react_agent.invoke(
            {"messages": [{"role": "user", "content": user_input}]},
            config=config,
        )

        # 마지막 AI 메시지 출력
        last_msg = result["messages"][-1]
        print(f"\nAgent: {last_msg.content}\n")


if __name__ == "__main__":
    main()
