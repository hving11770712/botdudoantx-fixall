import os
from telegram import Update
from lenh.chatmenber import on_my_chat_member
from telegram.ext import Application, CommandHandler, ChatMemberHandler
from lenh.status import status
from lenh.help import help_command
from lenh.ban import ban, unban
from lenh.tb import tb
from lenh.botout import out, unout, groups, list_blocked
from lenh.taikhoan import taikhoan 
from lenh.key import key_command
from lenh.naptien import naptien_command
from lenh.start import start
from lenh.buymodel import model, buymodel, history
from lenh.code import code_command
from lenh.stop import stop 
from lenh.ref import ref
from lenh.stopall import stopall
from admin.admin import admin_command
from admin.createkey import createkey_command
from admin.resetkey import resetkey_command
from admin.giftcode import giftcode_command
from admin.xtnaptien import xtnaptien_command
from admin.balance import balance_command
from admin.listkeys import listkeys_command
from admin.backup import backup_command
from admin.check import check_command
from lenh.config import TOKEN, clean_expired_models, error_handler

from game.sunwin.modelbasic import modelbasic_command




# Hàm main
def main():
    clean_expired_models()
    application = Application.builder().token(TOKEN).build()

    # Handler game 
    # application.add_handler(CommandHandler("md5hit", md5hit_command))
    application.add_handler(CommandHandler("modelbasic", modelbasic_command))
    # application.add_handler(CommandHandler("modelvip", modelvip))
    application.add_handler(CommandHandler("stop", stop))

    # Handler nhóm
    application.add_handler(ChatMemberHandler(on_my_chat_member, ChatMemberHandler.MY_CHAT_MEMBER))
    application.add_handler(CommandHandler("out", out))
    application.add_handler(CommandHandler("unout", unout))
    application.add_handler(CommandHandler("list", list_blocked))
    application.add_handler(CommandHandler("groups", groups))

    # Handler người dùng
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("ref", ref))
    application.add_handler(CommandHandler("model", model))
    application.add_handler(CommandHandler("buymodel", buymodel))
    application.add_handler(CommandHandler("naptien", naptien_command))
    application.add_handler(CommandHandler("key", key_command))
    application.add_handler(CommandHandler("taikhoan", taikhoan))
    application.add_handler(CommandHandler("code", code_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("history", history))

    # Handler admin
    application.add_handler(CommandHandler("balance", balance_command))
    application.add_handler(CommandHandler("admin", admin_command))
    application.add_handler(CommandHandler("listkeys", listkeys_command))
    application.add_handler(CommandHandler("stopall", stopall))
    application.add_handler(CommandHandler("backup", backup_command))
    application.add_handler(CommandHandler("createkey", createkey_command))
    application.add_handler(CommandHandler("giftcode", giftcode_command))
    application.add_handler(CommandHandler("xtnaptien", xtnaptien_command))
    application.add_handler(CommandHandler("status", status))
    application.add_handler(CommandHandler("tb", tb))
    application.add_handler(CommandHandler("check", check_command))

    # Handler ban
    application.add_handler(CommandHandler("ban", ban))
    application.add_handler(CommandHandler("unban", unban))
    application.add_handler(CommandHandler("resetkey", resetkey_command))

    # Handler lỗi
    application.add_error_handler(error_handler)

    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    os.system("clear")
    main()