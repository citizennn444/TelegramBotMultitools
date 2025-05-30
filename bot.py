import random
import re
import io
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputFile
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    ConversationHandler,
    filters
)
import qrcode

TOKEN = 'TON_TOKEN_ICI'

PREFIXES = {
    'free': ['06 95', '07 56', '07 58'],
    'bouygues': ['06 60', '06 61', '07 81'],
    'sfr': ['06 10', '06 11', '07 69']
}

SELECT_COUNT = range(1)
user_choice = {}

def generate_numbers(prefix_list, count=10):
    numbers = []
    for _ in range(count):
        prefix = random.choice(prefix_list).replace(" ", "")
        suffix = "".join([str(random.randint(0, 9)) for _ in range(6)])
        numbers.append(f"{prefix}{suffix}")
    return numbers

def detect_operator(number):
    for op, prefixes in PREFIXES.items():
        for p in prefixes:
            clean = p.replace(" ", "")
            if number.startswith(clean[:4]):
                return op.capitalize()
    return "Inconnu"

def validate_number(number):
    return bool(re.match(r'^0[67]\d{8}$|^\+33[67]\d{8}$', number))

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("Générer Free", callback_data='gen_free')],
        [InlineKeyboardButton("Générer Bouygues", callback_data='gen_bouygues')],
        [InlineKeyboardButton("Générer SFR", callback_data='gen_sfr')],
        [InlineKeyboardButton("Ajouter +33", callback_data='add33'),
         InlineKeyboardButton("Supprimer +33", callback_data='remove33')],
        [InlineKeyboardButton("Vérifier numéros", callback_data='verif'),
         InlineKeyboardButton("Détecter opérateur", callback_data='detect')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "Bienvenue sur le Multitools Telco !\n\nChoisis une action ci-dessous :",
        reply_markup=reply_markup
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    command = query.data
    cmd_clean = command.replace('gen_', '')
    user_choice[query.message.chat_id] = cmd_clean

    if command.startswith("gen_"):
        await query.message.reply_text("📥 Combien de numéros veux-tu générer ? (entre 1 et 100)")
    else:
        await query.message.reply_text("📥 Envoie maintenant les numéros (1 par ligne ou séparés par espace) :")
    return SELECT_COUNT

async def send_generated(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    command = user_choice.get(chat_id)
    text = update.message.text.strip()

    if not command:
        await update.message.reply_text("⚠️ Aucune commande sélectionnée. Clique d'abord sur un bouton.")
        return ConversationHandler.END

    if command in ['free', 'bouygues', 'sfr']:
        try:
            count = int(text)
            if not 1 <= count <= 100:
                raise ValueError
        except ValueError:
            await update.message.reply_text("Merci d'entrer un nombre entre 1 et 100.")
            return SELECT_COUNT

        numbers = generate_numbers(PREFIXES[command], count)
        number_list = "\n".join(numbers)

        txt_buffer = io.StringIO(number_list)
        await update.message.reply_document(document=InputFile(txt_buffer, filename=f"{command}_{count}_numeros.txt"))

        img = qrcode.make(number_list)
        img_buffer = io.BytesIO()
        img.save(img_buffer, format='PNG')
        img_buffer.seek(0)
        await update.message.reply_photo(photo=InputFile(img_buffer, filename="qr.png"), caption=f"Numéros {command.capitalize()} générés")

    elif command == 'verif':
        raw_numbers = re.findall(r'(\+33[67]\d{8}|0[67]\d{8})', text.replace("\n", " "))
        valid = [num for num in raw_numbers if validate_number(num)]
        invalid = [num for num in text.replace("\n", " ").split() if num not in valid]
        msg = f"✅ Valides ({len(valid)}):\n" + "\n".join(valid)
        if invalid:
            msg += f"\n\n❌ Invalides ({len(invalid)}):\n" + "\n".join(invalid)
        await update.message.reply_text(msg)

    elif command == 'detect':
        raw_numbers = re.findall(r'(\+33[67]\d{8}|0[67]\d{8})', text.replace("\n", " "))
        result = []
        for number in raw_numbers:
            normalized = number
            if number.startswith("+33"):
                normalized = f"0{number[3:]}"
            result.append(f"{number} → {detect_operator(normalized)}")
        await update.message.reply_text("\n".join(result) if result else "Aucun numéro valide détecté.")

    elif command == 'add33':
        raw = re.findall(r'(0[67]\d{8})', text.replace("\n", " "))
        result = [f'+33{num[1:]}' for num in raw]
        msg = "📞 Avec +33 :\n" + "\n".join(result) if result else "Aucun numéro 06/07 détecté."
        await update.message.reply_text(msg)

    elif command == 'remove33':
        raw = re.findall(r'\+33([67]\d{8})', text.replace("\n", " "))
        result = [f'0{match}' for match in raw]
        msg = "📞 Sans +33 :\n" + "\n".join(result) if result else "Aucun numéro +33 détecté."
        await update.message.reply_text(msg)

    else:
        await update.message.reply_text("Commande inconnue ou expirée.")

    return ConversationHandler.END

def main():
    app = ApplicationBuilder().token(TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(button_handler)],
        states={SELECT_COUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, send_generated)]},
        fallbacks=[]
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(conv_handler)
    app.add_handler(CallbackQueryHandler(button_handler))

    print("✅ Bot en ligne !")
    app.run_polling()

if __name__ == '__main__':
    main()
