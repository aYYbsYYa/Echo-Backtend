from app import create_app

app = create_app()

if __name__ == "__main__":
    # 打印所有路由
    print("\n=== 已注册的路由 ===")
    for rule in app.url_map.iter_rules():
        print(f"{rule.methods} {rule.rule} -> {rule.endpoint}")
    print("=" * 50 + "\n")
    
    app.run(
        host="0.0.0.0",
        port=app.config["PORT"],
        debug=app.config["DEBUG"],
        use_reloader=False,
    )
