function getTimeInTimezone(timezone) {
    const now = new Date();
    const options = {
        timeZone: timezone,
        weekday: 'long',
        year: 'numeric',
        hour12: false,
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
    };

    const formatter = new Intl.DateTimeFormat('en-US', options);
    return formatter.format(now);
}

