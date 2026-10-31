module.exports = {
  startUser(context, events, done) {
    context.vars.loadDeadline = Date.now() + 60000;
    done();
  },

  keepRunning(context, next) {
    next(Date.now() < context.vars.loadDeadline);
  },

  attachToken(requestParams, context, events, done) {
    const token = process.env.ATTENDFLOW_LOAD_TOKEN;
    if (!token) return done(new Error("Load-test token is missing"));
    requestParams.headers = requestParams.headers || {};
    requestParams.headers.Authorization = token;
    done();
  },

  checkStatus(requestParams, response, context, events, done) {
    if (response.statusCode !== 200) {
      events.emit("counter", "unexpected_status", 1);
    }
    done();
  }
};