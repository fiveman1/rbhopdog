import json

def main():
    with open("README.md", "w") as file:
        file.write(
"""# rbhopdog

discord.py bot that uses primarily the strafes.net api to access data from rbhop/rsurf among other things

Commands:
"""
        )

        with open("src/files/help.json") as help:
            commands = json.load(help)

        for cmd in sorted(commands.keys()):
            args = commands[cmd]["args"]
            blurb = commands[cmd]["blurb"]
            if args:
                arg_str = f"{cmd} {args}"
            else:
                arg_str = cmd
            file.write(
f"""
**!{arg_str}**

    {blurb}
"""
            )

if __name__ == "__main__":
    main()
