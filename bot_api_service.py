#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import config
import logging
import telebot
from flask import Flask, request
from flask_restful import Api, Resource, reqparse

logging.basicConfig()

app = Flask(__name__)
api = Api(app)

pipelines = {}
'''
{
  1234: {
    'pipeline_id': 1234,
    ...
    'message_id': 123456,
  }
}
'''

icon = {
    'failed': '❌',
    'success': '✅',
    'canceled': '⏹',
    'running': '▶️',
    'created': '⏸️',
    'skipped': '⏭️',
    'manual': '✋',
    'pending': '🕒️',
    'other': '❔',
}

def update_message(pipeline):

    text = prepare_text(pipeline)
    try:
        msg = bot.edit_message_text(
            text,
            chat_id = chat_id,
            message_id = pipeline.message_id,
            parse_mode = "Markdown",
            disable_web_page_preview = "yes"
        )
    except Exception as e:
        logging.error(e)
        return

    return True

def send_message(pipeline):

    text = prepare_text(pipeline)
    try:
        msg = bot.send_message(
            chat_id,
            text,
            parse_mode = "Markdown",
            disable_web_page_preview = "yes"
        )
    except Exception as e:
        logging.error(e)
        return

    return msg.message_id

def prepare_text(pipeline):

    jobs = []
    for job_id, job in pipeline.jobs.items():
        duration_text = f"{job.duration} seconds" if job.duration > 0 else ""
        jobs.append(f"{job.name}: [{icon.get(job.status, '❔')}]({pipeline.url}/-/jobs/{job_id}) {duration_text}")
    jobs = "\n".join(jobs)

    duration_text = f"{pipeline.duration} seconds" if pipeline.duration >0 else ""
    text = (
        f'🔥 *{pipeline.namespace}/{pipeline.name}*\n'
        f'🙂 {pipeline.username}\n'
        f'```\n'
        f'⎇ {pipeline.ref}\n'
        f'{pipeline.commit_message}\n'
        f'```\n'
        f'{jobs}\n\n'
        f'[{icon.get(pipeline.status, "")}]({pipeline.url}/pipelines/{pipeline._id}) {duration_text}'
    )
    return text

class Job(object):
    def __init__(self, data={}):
        self.pipeline_id = data.get('commit', {}).get('id')
        self._id = data.get('build_id')
        self.status = data.get('build_status')
        self.name = data.get('build_name')
        self.duration = data.get('build_duration')
        if not self.duration:
            self.duration = 0

    def __repr__(self):
        return self.__str__()

    def __str__(self):
        return ', '.join([f'{key}={self.__dict__.get(key)}' for key in self.__dict__])


class Pipeline(object):
    def __init__(self, data):
        attr = data.get('object_attributes', {})
        self._id = attr.get('id')
        self.attr = data.get('object_attributes', {})
        self.ref = attr.get('ref')
        self.status = attr.get('status')
        self.duration = attr.get('duration')
        if not self.duration:
            self.duration = 0

        project = data.get('project', {})
        self.name = project.get('name')
        self.namespace = project.get('namespace')
        self.url = project.get('web_url')

        self.username = data.get('user', {}).get('name')
        self.commit_message = data.get('commit', {}).get('message')

        self.jobs = {}
        for build in data.get('builds'):
            job = Job()
            job._id = build.get('id')
            job.status = build.get('status')
            job.name = build.get('name')
            job.pipeline_id = self._id
            self.jobs[job._id] = job

    def __repr__(self):
        return self.__str__()

    def __str__(self):
        return ', '.join([f'{key}={self.__dict__.get(key)}' for key in self.__dict__])

class GitMessage(Resource):
    def get(self):
        return "Nothing", 404

    def post(self,chat):

        data = request.get_json()
        event = request.headers.get('X-Gitlab-Event')

        if event == 'Pipeline Hook':
            pipeline = Pipeline(data)
            #builds = sorted(data.get('builds'), key=lambda k: k['id'])

            if pipeline._id in pipelines.keys():
                current_pipeline = pipelines[pipeline._id]
                current_pipeline.status = pipeline.status
                current_pipeline.duration = pipeline.duration
                status = update_message(current_pipeline)
                if status:
                    return "Message_sent"
                else:
                    return "Message not sent", 404
            else:
                message_id = send_message(pipeline)
                pipeline.message_id = message_id
                pipelines[pipeline._id] = pipeline
                if message_id:
                    return "Message sent"
                else:
                    return "Message not sent", 404

        elif event == 'Job Hook':
            job = Job(data)
            pipeline = pipelines.get(job.pipeline_id)
            if not pipeline:
                logging.warning('pipeline not found')
                return "Message not sent", 404
            p_job = pipeline.jobs.get(job._id)
            if p_job:
                p_job.status = job.status
                p_job.duration = int(float(job.duration))


            status = update_message(pipeline)

            if status:
                return "Message sent"
            else:
                return "Message not sent", 404

        else:
            return "Hook is not supported", 404


    def put(self):
        return "Use POST to send message", 404

    def delete(self):
        return "Nothing", 404

if __name__ == "__main__":

    bot = telebot.TeleBot(config.token)

    api.add_resource(GitMessage, "/git/<string:chat>")
    app.run(debug=True, host="0.0.0.0")
