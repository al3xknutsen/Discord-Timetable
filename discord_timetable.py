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


client = commands.Bot(command_prefix=commands.when_mentioned_or("!", "/"), description="Timeplan og deadlines")


def get_weekday_index(weekday):
    if weekday in day_name:
        list_days = day_name
    elif weekday in day_abbr:
        list_days = day_abbr
    elif weekday in day_name_NOR:
        list_days = day_name_NOR
    elif weekday in day_abbr_NOR:
        list_days = day_abbr_NOR
    else:
        return False
    return list_days.index(weekday)


def get_today(day=datetime.now().weekday()):
    now = datetime.now()
    week = now.isocalendar()[1]

    if day < datetime.now().weekday():
        week += 1

    db_timetable = sqlite3.connect("timetable.db")
    c = db_timetable.cursor()

    subjects_today = c.execute("SELECT * FROM timetable WHERE day = ? AND week = ? ORDER BY time",
                               (day, week)).fetchall()

    db_timetable.close()

    if day == datetime.today().weekday() and day <= 4 and \
                    now.time() > datetime.strptime(subjects_today[-1][4].split("-")[1], "%H:%M").time():
        day += 1
    if day > 4:
        day = 0
        week += 1

    return [week, day]


@client.command(pass_context=True, description="Viser ei liste over alle deadlines", hidden=True)
async def deadlines(context):
    pass


@client.command(pass_context=True, description="Viser timeplan",
                aliases=["tt", "timeplan", "tiddy", "timepl0x", "tiddysprinkles"])
async def timetable(context, weekday: str=""):
    padding_width = [[3], [3], [3], [4]]

    db_timetable = sqlite3.connect("timetable.db")
    c = db_timetable.cursor()

    if weekday:
        weekday = weekday.lower()
        if weekday == "week":
            pass
        else:
            day = get_weekday_index(weekday)
            if day is False:
                await client.send_message(context.message.channel, "Ugyldig dag")
                return
    else:
        day = datetime.today().weekday()

    week, day = get_today(day)

    subjects_today = c.execute("SELECT * FROM timetable WHERE day = ? AND week = ? ORDER BY time",
                               (day, week)).fetchall()

    for subject in subjects_today:
        padding_width[0].append(len(subject_codes[subject[2]]))
        padding_width[1].append(len(subject[4]))
        padding_width[2].append(len(subject[3]))
        padding_width[3].append(len(lecture_types[subject[5]]))

    response_title = "Timeplan for {0} uke {1}\n".format(day_name_NOR[day], str(week))

    response_header = "```[#] {0} | {1} | {2} | {3}\n".format("Fag".ljust(max(padding_width[0])),
                                                        "Tid".ljust(max(padding_width[1])),
                                                        "Rom".ljust(max(padding_width[2])),
                                                        "Type".ljust(max(padding_width[3])))
    response_line = "-" * len(response_header) + "\n"

    response = response_title + response_header + response_line

    for i, subject in enumerate(subjects_today):
        response += "[{0}] {1} | {2} | {3} | {4}\n".format(i + 1,
                                                           subject_codes[subject[2]].ljust(max(padding_width[0])),
                                                           subject[4].ljust(max(padding_width[1])),
                                                           subject[3].ljust(max(padding_width[2])),
                                                           lecture_types[subject[5]].ljust(max(padding_width[3])))
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


@client.command(pass_context=True, description="Sier ifra at du blir borte en forelesning", aliases=["absent"])
async def absence(context):
    now = datetime.now()

    msg = context.message.content.split()

    if len(msg) < 2:
        await client.send_message(context.message.channel, "Du må angi et tall for hvilken forelesning du er borte "
                                                           "fra! (Bruk !timetable for å finne riktig nummer)")
        return

    if len(msg) == 3:
        day = get_weekday_index(msg[2])
        if day is False:
            await client.send_message(context.message.channel, "Ugyldig dag")
            return
    else:
        day = now.weekday()

    week, day = get_today(day)

    db_absence = sqlite3.connect("absence.db")
    c = db_absence.cursor()

    db_timetable = sqlite3.connect("timetable.db")
    d = db_timetable.cursor()

    lecture = d.execute("SELECT * FROM timetable WHERE week = ? AND day = ? ORDER BY time",
                        (week, day)).fetchall()[int(msg[1]) - 1]

    already_absent = c.execute("SELECT * FROM absence WHERE week = ? AND day = ? AND subject = ? AND time = ? AND "
                               "student = ?", (week, day, lecture[2], lecture[4],
                                               context.message.author.id)).fetchall()
    if len(already_absent) > 0:
        await client.send_message(context.message.channel, "Du har allerede registrert fravær for denne forelesningen!")
        return

    c.execute("INSERT INTO absence VALUES (?, ?, ?, ?, ?)", (week, day, lecture[2], lecture[4],
              context.message.author.id))

    await client.send_message(context.message.channel, "{0} registrerte fravær for {1} kl. {2}, {3} uke {4}".format(
        context.message.author.name, subject_codes[lecture[2]], lecture[4], day_name_NOR[day], week
    ))

    db_absence.commit()
    db_absence.close()
    db_timetable.close()


@client.command(pass_context=True, description="Angrer fravær", hidden=True)
async def removeabsence(context):
    week, day = get_today()

    db_absence = sqlite3.connect("absence.db")
    c = db_absence.cursor()

    c.execute("SELECT * FROM absence WHERE week = ? AND day = ? AND subject = ? AND time = ? AND student = ?",
              ())

    db_absence.commit()
    db_absence.close()


@client.command(pass_context=True, description="Viser alle fravær", hidden=True)
async def checkabsence(context):
    db_absence = sqlite3.connect("absence.db")
    c = db_absence.cursor()

    c.execute("SELECT * FROM checkin WHERE day = ? and week = ?",
              (datetime.today().weekday(), datetime.isocalendar()[1])).fetchall()

    await client.send_message(context.message.channel, "Fravær i dag:")
    # PRINT ABSENCE

    db_absence.close()


@client.command(pass_context=True, description="Shows timetable", hidden=True)
async def level(context):
    pass

client.run(sys.argv[1])
