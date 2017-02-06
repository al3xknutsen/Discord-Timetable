import asyncio, sys#, json
from datetime import datetime
from calendar import day_name, day_abbr
import sqlite3
from discord.ext import commands

subject_codes = {
    "TMA4115": "Matte 3",
    "TDT4100": "OOP",
    "TDT4112": "Proglab",
    "TFE4101": "Krets"
}

lecture_types = {
    "F": "Forelesning",
    "OF": "Øvingsforelesning",
    "O": "Øving",
    "L": "Lab",
    "LF": "Labforelesning",
    "S": "Sal"
}

day_name = [day.lower() for day in day_name]
day_abbr = [day.lower() for day in day_abbr]
day_name_NOR = ["mandag", "tirsdag", "onsdag", "torsdag", "fredag", "lørdag", "søndag"]
day_abbr_NOR = [day[:3] for day in day_name_NOR]


client = commands.Bot(command_prefix=commands.when_mentioned_or("!", "/"), description="Timetable and deadlines")


@client.command(pass_context=True, description="Lists all exercise deadlines", hidden=True)
async def deadlines(context):
    await client.send_message(context.message.channel, "__LIST_OF_DEADLINES__")


@client.command(pass_context=True, description="Viser timeplan", aliases=["tt", "timeplan", "tiddy", "timepl0x",
                                                                          "tiddysprinkles"])
async def timetable(context):
    padding_width = [10, 11, 8, 15]

    #with open("timetable.json") as db_timetable:
    #    timetable = json.load(db_timetable)

    db_timetable = sqlite3.connect("timetable.db")
    c = db_timetable.cursor()

    msg = context.message.content.split()
    if len(msg) > 1:
        arg = msg[1].lower()
        if arg == "week":
            pass
        else:
            if arg in day_name:
                list_days = day_name
            elif arg in day_abbr:
                list_days = day_abbr
            elif arg in day_name_NOR:
                list_days = day_name_NOR
            elif arg in day_abbr_NOR:
                list_days = day_abbr_NOR
            else:
                return
            day = list_days.index(arg)
    else:
        day = datetime.today().weekday()

    weeknumber = datetime.today().isocalendar()[1]
    if day < datetime.today().weekday():
        weeknumber += 1

    subjects_today = c.execute("SELECT * FROM timetable WHERE day = ? AND week = ? ORDER BY time",
                               (day, weeknumber)).fetchall()

    if day == datetime.today().day and day <= 4 and datetime.now().time() >\
            datetime.strptime(subjects_today[-1][4].split("-")[1], "%H:%M").time():
        day += 1
    if day > 4:
        day = 0
        weeknumber += 1
    subjects_today = c.execute("SELECT * FROM timetable WHERE day = ? AND week = ? ORDER BY time",
                               (day, weeknumber)).fetchall()

    #if day > 4:
    #    await client.send_message(context.message.channel, "Helg! :smile:")
    #    return

    await client.send_message(context.message.channel, "Timeplan for " + day_name_NOR[day] + " uke " + str(weeknumber))

    response = "```    {0} | {1} | {2} | {3}\n".format("Fag".ljust(padding_width[0]), "Tid".ljust(padding_width[1]),
                                              "Rom".ljust(padding_width[2]), "Type".ljust(padding_width[3]))
    response += "-" * len(response) + "\n"

    for i, subject in enumerate(subjects_today):
        response += "({0}) {1} | {2} | {3} | {4}\n".format(i, subject_codes[subject[2]].ljust(padding_width[0]),
                                                subject[4].ljust(padding_width[1]),
                                                subject[3].ljust(padding_width[2]),
                                                lecture_types[subject[5]].ljust(padding_width[3]))
        response += "```"

    await client.send_message(context.message.channel, response)

    #await client.send_message(context.message.channel, "```"+str(timetable)+"```")
    db_timetable.close()


@client.command(pass_context=True, description="Checks you in to the current lesson, indicating that you have arrived")
async def checkin(context):
    db_timetable = sqlite3.connect("timetable.db")
    c = db_timetable.cursor()

    now = datetime.now()
    week = now.isocalendar()[1]
    weekday = now.weekday()

    subjects_today = c.execute("SELECT * FROM timetable WHERE day = ? AND week = ?",
                               (weekday, week)).fetchall()

    for subject in subjects_today:
        start, finish = [datetime.strptime(t, "%H:%M").time() for t in subject[4].split("-")]
        in_lecture = False

        if start < now.time() < finish:
            in_lecture = True

            now_format = now.strftime("%H:%M")
            db_checkin = sqlite3.connect("checkin.db")
            d = db_checkin.cursor()

            already_checkedin = d.execute("SELECT * FROM checkin WHERE day = ? AND week = ? AND subject = ? AND "
                                          "time = ? AND student = ?", (weekday, week, subject[2], subject[4],
                                                                       context.message.author.id)).fetchall()

            if len(already_checkedin) > 0:
                await client.send_message(context.message.channel,
                                          "Du har allerede sjekket inn for denne forelesningen!")
                break

            d.execute("INSERT INTO checkin VALUES (?, ?, ?, ?, ?, ?)",
                      (week, weekday, subject[2], subject[4], context.message.author.id, now_format))

            db_checkin.commit()
            db_checkin.close()

            await client.send_message(context.message.channel, context.message.author.name + " sjekket inn for " +
                                      subject_codes[subject[2]] + " kl. " + now_format)
            break

    if not in_lecture:
        await client.send_message(context.message.channel, "Ingen forelesninger atm")

    db_timetable.close()


@client.command(pass_context=True, description="Viser alle innsjekkinger", hidden=True)
async def checkcheckin(context):
    db_checkin = sqlite3.connect("checkin.db")
    c = db_checkin.cursor()

    c.execute("SELECT * FROM checkin WHERE day = ? and week = ?",
              (datetime.today().weekday(), datetime.isocalendar()[1])).fetchall()

    await client.send_message(context.message.channel, "Innsjekkinger i dag:")
    # PRINT CHECKINS

    db_checkin.close()


@client.command(pass_context=True, description="Sier ifra at du blir borte en forelesning", hidden=True)
async def absence(context):
    msg = context.message.content.split()
    if len(msg) < 2:
        await client.send_message(context.message.channel, "Du må angi et tall for hvilken forelesning du er borte"
                                                           "fra! (Bruk !timetable for å finne riktig nummer")
        return

    db_absence = sqlite3.connect("absence.db")
    c = db_absence.cursor()

    #c.execute("INSERT INTO absence VALUES (?, ?, ?, ?, ?)", )

    db_absence.commit()
    db_absence.close()


@client.command(pass_context=True, description="Angrer fravær", hidden=True)
async def removeabsence(context):
    pass


@client.command(pass_context=True, description="Viser alle fravær", hidden=True)
async def checkabsence(context):
    db_absence = sqlite3.connect("absence.db")
    c = db_absence.cursor()

    c.execute("SELECT * FROM checkin WHERE day = ? and week = ?",
              (datetime.today().weekday(), datetime.isocalendar()[1])).fetchall()

    await client.send_message(context.message.channel, "Fravær i dag:")
    # PRINT ABSENCE

    db_absence.close()


# @client.command(pass_context=True, description="Shows timetable")
# async def tt(context):
#     timetable(context)

client.run(sys.argv[1])
