from packages import create_framework


def main():
    framework = create_framework()
    print(
        "NekoBot framework ready "
        f"(schemas={len(framework.schema_registry.list())}, "
        f"plugins={len(framework.runtime_registry.plugins)}, "
        f"providers={len(framework.runtime_registry.providers)})"
    )


if __name__ == "__main__":
    main()
