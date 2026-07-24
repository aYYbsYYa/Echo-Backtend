"""
灵笺后端API测试脚本
测试所有核心功能：创建对话、发送消息、模式切换、人格画像
"""

import json
import time
from urllib.request import Request, urlopen
from urllib.error import HTTPError


BASE_URL = "http://localhost:3000"
TEST_USER_ID = "test_user_echo_001"


def make_request(method: str, path: str, data: dict = None) -> dict:
    """发送HTTP请求"""
    url = f"{BASE_URL}{path}"
    headers = {"Content-Type": "application/json"}
    
    if data:
        request = Request(
            url,
            data=json.dumps(data).encode("utf-8"),
            headers=headers,
            method=method,
        )
    else:
        request = Request(url, headers=headers, method=method)
    
    try:
        with urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as e:
        error_body = e.read().decode("utf-8")
        print(f"❌ HTTP Error {e.code}: {error_body}")
        raise
    except Exception as e:
        print(f"❌ Request failed: {e}")
        raise


def test_create_conversation():
    """测试1: 创建灵笺对话（倾听模式）"""
    print("\n【测试1】创建灵笺对话（倾听模式）")
    print("-" * 50)
    
    response = make_request(
        "POST",
        "/api/echo/conversations",
        {"user_id": TEST_USER_ID, "mode": "listen"}
    )
    
    assert "data" in response, "响应缺少data字段"
    conversation = response["data"]
    assert conversation["user_id"] == TEST_USER_ID, "用户ID不匹配"
    assert conversation["mode"] == "listen", "模式应为listen"
    assert "id" in conversation, "缺少对话ID"
    
    print(f"✅ 创建成功")
    print(f"   对话ID: {conversation['id']}")
    print(f"   模式: {conversation['mode']}")
    
    return conversation["id"]


def test_send_message_listen_mode(conversation_id: str):
    """测试2: 倾听模式对话"""
    print("\n【测试2】倾听模式对话")
    print("-" * 50)
    
    test_messages = [
        "我最近总是拖延，明明知道该做什么，就是不想动...",
        "我觉得是因为害怕做不好，所以不敢开始",
        "但拖延让我更焦虑了"
    ]
    
    for i, msg in enumerate(test_messages, 1):
        print(f"\n第{i}轮对话:")
        print(f"用户: {msg}")
        
        response = make_request(
            "POST",
            f"/api/echo/conversations/{conversation_id}/messages",
            {"content": msg}
        )
        
        assert "data" in response, "响应缺少data字段"
        data = response["data"]
        assert "assistant_message" in data, "缺少AI回复"
        
        ai_reply = data["assistant_message"]["content"]
        print(f"灵笺: {ai_reply}")
        
        time.sleep(1)  # 避免请求过快
    
    print("\n✅ 倾听模式对话测试通过")


def test_get_conversation(conversation_id: str):
    """测试3: 获取对话详情"""
    print("\n【测试3】获取对话详情")
    print("-" * 50)
    
    response = make_request("GET", f"/api/echo/conversations/{conversation_id}")
    
    assert "data" in response, "响应缺少data字段"
    conversation = response["data"]
    assert "messages" in conversation, "缺少消息列表"
    assert len(conversation["messages"]) >= 6, "消息数量不足（应有至少3对）"
    
    print(f"✅ 对话详情获取成功")
    print(f"   消息数: {len(conversation['messages'])}")
    print(f"   当前模式: {conversation['mode']}")


def test_switch_to_mirror_mode(conversation_id: str):
    """测试4: 切换到镜像模式"""
    print("\n【测试4】切换到镜像模式")
    print("-" * 50)
    
    response = make_request(
        "PATCH",
        f"/api/echo/conversations/{conversation_id}/mode",
        {"mode": "mirror"}
    )
    
    assert "data" in response, "响应缺少data字段"
    conversation = response["data"]
    assert conversation["mode"] == "mirror", "模式切换失败"
    
    print(f"✅ 模式切换成功: listen → mirror")


def test_send_message_mirror_mode(conversation_id: str):
    """测试5: 镜像模式对话"""
    print("\n【测试5】镜像模式对话")
    print("-" * 50)
    
    test_messages = [
        "我该怎么办？",
        "你觉得我应该从哪里开始？"
    ]
    
    for i, msg in enumerate(test_messages, 1):
        print(f"\n第{i}轮对话:")
        print(f"用户: {msg}")
        
        response = make_request(
            "POST",
            f"/api/echo/conversations/{conversation_id}/messages",
            {"content": msg}
        )
        
        assert "data" in response, "响应缺少data字段"
        data = response["data"]
        assert "assistant_message" in data, "缺少AI回复"
        
        ai_reply = data["assistant_message"]["content"]
        print(f"灵笺（镜像）: {ai_reply}")
        
        time.sleep(1)
    
    print("\n✅ 镜像模式对话测试通过")


def test_get_user_conversations():
    """测试6: 获取用户所有对话"""
    print("\n【测试6】获取用户所有对话")
    print("-" * 50)
    
    response = make_request("GET", f"/api/echo/users/{TEST_USER_ID}/conversations")
    
    assert "data" in response, "响应缺少data字段"
    conversations = response["data"]
    assert len(conversations) > 0, "用户应至少有一个对话"
    
    print(f"✅ 用户对话列表获取成功")
    print(f"   对话数: {len(conversations)}")


def test_get_user_profile():
    """测试7: 获取用户人格画像"""
    print("\n【测试7】获取用户人格画像")
    print("-" * 50)
    
    response = make_request("GET", f"/api/echo/users/{TEST_USER_ID}/profile")
    
    assert "data" in response, "响应缺少data字段"
    profile = response["data"]
    
    if profile.get("status") == "insufficient_data":
        print(f"⚠️  对话数据不足，无法生成完整画像")
        print(f"   当前消息数: {profile.get('message_count', 0)}")
    else:
        print(f"✅ 人格画像生成成功")
        print(f"   消息数: {profile.get('message_count', 0)}")
        if "profile_data" in profile:
            traits = profile["profile_data"].get("traits", "无")
            print(f"   人格特征:\n{traits}")


def test_health_check():
    """测试0: 健康检查"""
    print("\n【测试0】后端健康检查")
    print("-" * 50)
    
    response = make_request("GET", "/api/health")
    assert response.get("data", {}).get("status") == "ok", "后端服务异常"
    
    print("✅ 后端服务正常运行")


def run_all_tests():
    """运行所有测试"""
    print("=" * 50)
    print("灵笺后端API测试套件")
    print("=" * 50)
    
    try:
        # 0. 健康检查
        test_health_check()
        
        # 1. 创建对话
        conversation_id = test_create_conversation()
        
        # 2. 倾听模式对话
        test_send_message_listen_mode(conversation_id)
        
        # 3. 获取对话详情
        test_get_conversation(conversation_id)
        
        # 4. 切换模式
        test_switch_to_mirror_mode(conversation_id)
        
        # 5. 镜像模式对话
        test_send_message_mirror_mode(conversation_id)
        
        # 6. 获取用户对话列表
        test_get_user_conversations()
        
        # 7. 获取人格画像
        test_get_user_profile()
        
        print("\n" + "=" * 50)
        print("✅ 所有测试通过！")
        print("=" * 50)
        
    except AssertionError as e:
        print(f"\n❌ 测试失败: {e}")
        return False
    except Exception as e:
        print(f"\n❌ 测试异常: {e}")
        return False
    
    return True


if __name__ == "__main__":
    print("\n⚠️  请确保：")
    print("   1. 后端服务已启动 (python main.py)")
    print("   2. .env 文件已配置 AI API 密钥")
    print("   3. 服务运行在 http://localhost:3000\n")
    
    print("开始测试...\n")
    
    success = run_all_tests()
    exit(0 if success else 1)
