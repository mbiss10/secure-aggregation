import argparse
import json
from flask import Flask, request, render_template

app = Flask(__name__)

insecure_data = []
secure_data = []


@app.route("/")
def index():
    return render_template("index.html")


@app.route('/result')
def show_result():
    args = request.args
    aggregate = f"{int(args['agg']):,}"
    return render_template("result.html", aggregate=aggregate)


@app.route('/report-insecure', methods=['POST'])
def get_plain_values():
    data = dict(request.form)
    print(data)
    insecure_data.append(data)
    return data


# @app.route('/report-my-perturbations', methods=['POST'])
# def receive_client_sent_perturbations():
#     data = dict(request.form)
#     print("receive_client_sent_perturbations: ", data)
#     # add this to secure data dict
#     return data


@app.route('/report-secure', methods=['POST'])
def get_masked_values():
    data = dict(request.form)

    perturbationMessages = {}
    for key in data:
        if "perturbationMessages" in key:
            perturbationMessages[key.replace(
                "perturbationMessages", "")] = data[key]

    data["perturbationMessages"] = perturbationMessages

    secure_data.append(data)
    return data


@app.route('/big-brother')
def big_brother_view():
    return render_template('big_brother.html', data=insecure_data)


@app.route('/secure-view')
def secure_agg_view():
    return render_template('secure_view.html', data=secure_data)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("-h", "--host",
                        help="Hostname", type=str)
    parser.add_argument("-p", "--port",
                        help="Port", type=int)

    args = parser.parse_args()

    host = args.host if args.host else "localhost"
    port = args.port if args.port else 8001

    app.run(host, port, debug=True)
