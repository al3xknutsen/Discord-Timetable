import asyncio, sys
from datetime import datetime
from calendar import day_name, day_abbr
import sqlite3
from discord.ext import commands
import discord.utils

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
                aliases=["tt", "timeplan", "tiddy", "timepl0x", "tiddysprinkles", "timetable_me_sempai", "horaro"])
async def timetable(context, day: str=""):
    padding_width = [[3], [3], [3], [4], [5], [3]]

    db_timetable = sqlite3.connect("timetable.db")
    c_timetable = db_timetable.cursor()

    if day:
        day = day.lower()
        if day == "week":
            pass
        else:
            day = get_weekday_index(day)
            if day is False:
                await client.send_message(context.message.channel, "Ugyldig dag")
                return
    else:
        day = datetime.today().weekday()

    week, day = get_today(day)

    students = set()

    subjects_today = c_timetable.execute("SELECT * FROM timetable WHERE day = ? AND week = ? ORDER BY time",
                                         (day, week)).fetchall()

    db_checkin = sqlite3.connect("checkin.db")
    c_checkin = db_checkin.cursor()

    db_absence = sqlite3.connect("absence.db")
    c_absence = db_absence.cursor()

    for student in c_checkin.execute("SELECT * FROM checkin GROUP BY student").fetchall():
        students.add(str(student[4]))
    for student in c_absence.execute("SELECT * FROM absence GROUP BY student").fetchall():
        students.add(str(student[4]))
    students = sorted(students)

    for subject in subjects_today:
        padding_width[0].append(len(subject_codes[subject[2]]))
        padding_width[1].append(len(subject[4]))
        padding_width[2].append(len(subject[3]))
        padding_width[3].append(len(lecture_types[subject[5]]))
        padding_width[4].append(len(students))
        padding_width[5].append(len(students))

    response_title = "TIMEPLAN FOR {0} UKE {1}\n-------------------\n".format(day_name_NOR[day].upper(), str(week))

    response_header = "```[#] {0} | {1} | {2} | {3} | {4} | {5}\n".format("Fag".ljust(max(padding_width[0])),
                                                                          "Tid".ljust(max(padding_width[1])),
                                                                          "Rom".ljust(max(padding_width[2])),
                                                                          "Type".ljust(max(padding_width[3])),
                                                                          "Chkin".ljust(max(padding_width[4])),
                                                                          "Abs".ljust(max(padding_width[5])))
    response_line = "-" * len(response_header) + "\n"

    response = response_title + response_header + response_line

    for i, subject in enumerate(subjects_today):
        mask_checkin = ""
        mask_absence = ""

        for student in students:
            checked_in = c_checkin.execute(
                "SELECT * FROM checkin WHERE day = ? AND week = ? AND subject = ? AND time = ? AND student = ?",
                (day, week, subject[2], subject[4], student)).fetchall()

            if checked_in:
                mask_checkin += "1"
            else:
                mask_checkin += "0"

            absent = c_absence.execute(
                "SELECT * FROM absence WHERE day = ? AND week = ? AND subject = ? AND time = ? AND student = ?",
                (day, week, subject[2], subject[4], student)).fetchall()

            if absent:
                mask_absence += "1"
            else:
                mask_absence += "0"

        response += "[{0}] {1} | {2} | {3} | {4} | {5} | {6}\n".\
            format(i + 1,
                   subject_codes[subject[2]].ljust(max(padding_width[0])),
                   subject[4].ljust(max(padding_width[1])),
                   subject[3].ljust(max(padding_width[2])),
                   lecture_types[subject[5]].ljust(max(padding_width[3])),
                   mask_checkin.ljust(max(padding_width[4])),
                   mask_absence.ljust(max(padding_width[5])))

    response += "```\n(MASK: {0})".format(", ".join([discord.utils.get(client.get_all_members(),
                                                                       id=user).name for user in students]))

    await client.send_message(context.message.channel, response)

    db_timetable.close()
    db_checkin.close()
    db_absence.close()


@client.command(pass_context=True, description="Indikerer at du har ankommet til nåværende forelesning")
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


@client.command(pass_context=True, description="Sier ifra at du blir borte en forelesning",
                aliases=["absent", "abs", "a"])
async def absence(context, number: int=0, day: str=""):
    now = datetime.now()
    day = day.lower()

    if day == "":
        day = now.weekday()
    else:
        day = get_weekday_index(day)

    if day is False:
        await client.send_message(context.message.channel, "Ugyldig dag")
        return

    week, day = get_today(day)

    db_absence = sqlite3.connect("absence.db")
    c = db_absence.cursor()

    db_timetable = sqlite3.connect("timetable.db")
    d = db_timetable.cursor()

    subjects_today = d.execute("SELECT * FROM timetable WHERE week = ? AND day = ? ORDER BY time",
                               (week, day)).fetchall()

    for i, subject in enumerate(subjects_today):
        start, finish = [datetime.strptime(t, "%H:%M").time() for t in subject[4].split("-")]

        if start < now.time() < finish:
            number = i + 1
            break

    if number < 1:
        await client.send_message(context.message.channel, "Ingen forelesninger atm.")
        return

    lecture = subjects_today[number - 1]

    already_absent = c.execute("SELECT * FROM absence WHERE week = ? AND day = ? AND subject = ? AND time = ? AND "
                               "student = ?", (week, day, lecture[2], lecture[4],
                                               context.message.author.id)).fetchall()
    if len(already_absent) > 0:
        await client.send_message(context.message.channel, "Du har allerede registrert fravær for denne forelesningen!")
        return

    c.execute("INSERT INTO absence VALUES (?, ?, ?, ?, ?)", (week, day, lecture[2], lecture[4],
              context.message.author.id))

    await client.send_message(context.message.channel, "{0} registrerte fravær for {1} kl. {2}, {3} uke {4}".format(
        context.message.author.name, subject_codes[lecture[2]], lecture[4], day_name_NOR[day], week))

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


@client.command(pass_context=True, description="Viser alle fravær", aliases=["ca"])
async def checkabsence(context, day: str=""):
    now = datetime.now()
    day = day.lower()

    if day == "":
        day = now.weekday()
    else:
        day = get_weekday_index(day)

    if day is False:
        await client.send_message(context.message.channel, "Ugyldig dag")
        return

    week, day = get_today(day)

    db_absence = sqlite3.connect("absence.db")
    c = db_absence.cursor()

    absence_today = c.execute("SELECT * FROM absence WHERE day = ? and week = ?",
                              (day, week)).fetchall()

    if not len(absence_today):
        response = "Ingen har meldt fravær "
        if now.day == day:
            response += "i dag."
        else:
            response += "for {0} uke {1}.".format(day_name_NOR[day], week)
        await client.send_message(context.message.channel, response)
        return

    subjects = set([sub[2] for sub in absence_today])

    response = "Fravær for {0} uke {1}:\n".format(day_name_NOR[day], week)

    for subject in subjects:
        user_ids = list([str(a[4]) for a in absence_today if a[2] == subject])
        usernames = [discord.utils.get(client.get_all_members(), id=user).name for user in user_ids]

        response += "- {0}: {1}\n".format(subject_codes[subject], ", ".join(usernames))

    await client.send_message(context.message.channel, response)

    db_absence.close()


@client.command(pass_context=True, description="Shows timetable", hidden=True)
async def level(context):
    pass

client.run(sys.argv[1])
