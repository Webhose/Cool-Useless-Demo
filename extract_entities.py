import webhose, operator, time, Queue, json, httplib, urllib, urllib2
from difflib import SequenceMatcher
from datetime import datetime, timedelta

# get your free access token from Webhose.io
webhose.config(token="XXXX-XXXXX-XXX-XXXX-XXXX")

dup_check = set()
image_cache = {}
person_queue = Queue.Queue(100)


# Return a score about how similar two strings are
def similar(a, b):
    return SequenceMatcher(None, a, b).ratio()


# Query Bing Image Search API for the facial image of a person
def get_image(search_string):

    if search_string in image_cache:
        return image_cache[search_string]

    headers = {
        # Request headers
        'Content-Type': 'multipart/form-data',
        'Ocp-Apim-Subscription-Key': 'XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX', # get your key from Bing API
    }

    try:
        params = urllib.urlencode({"q":'"' + search_string + '"', "count":10,"offset":0,"mkt":"en-us", "size":"small", "imageType":"Photo","imageContent":"Face"})
    except Exception:
        return None

    try:
        conn = httplib.HTTPSConnection('api.cognitive.microsoft.com')
        conn.request("POST", "/bing/v5.0/images/search?%s" % params, "{body}", headers)
        response = conn.getresponse()
        data = response.read()
        conn.close()
        for i in range(len(json.loads(data)['value'])):
            res = None
            try:
                content_url = json.loads(data)['value'][i]['contentUrl']
                req = urllib2.Request(content_url)
                res = urllib2.urlopen(req)
            except Exception:
                continue

            final_url = res.geturl()
            image_cache[search_string] = final_url
            return final_url


    except Exception as e:
        print("Error getting image")
        return None


# Given a list of posts, extract the top 5 names mentioned in the posts
def get_top_persons(posts, original_person):
    persons = {}
    for post in posts:
        for person in post.persons:
            name = person['name'].title()  # Capitalize
            # Don't count names that are either the name originating the posts, or similar, or only first name
            if (name == original_person) or (similar(original_person, name) > 0.8) or (name in original_person) or (" " not in name):
                continue

            if name in persons:
                persons[name] += 1
            else:
                persons[name] = 1

    # Sort the list of names
    sorted_persons = sorted(persons.items(), key=operator.itemgetter(1))
    sorted_persons.reverse()

    final_list = []
    # cleaning names that are part of a full name
    for person in sorted_persons:
        found_match = False
        if not " " in person[0]:
            for test_person in sorted_persons:
                if test_person[0] == person[0]:
                    continue

                if person[0] in test_person[0]:
                    found_match = True
                    break

        if found_match is False:
            final_list.append(person[0])

        if len(final_list) == 5:
            return final_list

    return final_list


# Search Webhose.io API over the past 30 days, for posts mentioning a name, and collect the posts to extract the top posts from
def extract_top_persons(top_person):
    top_person = top_person.title()
    print "extract_top_persons for " + top_person
    days_back = 30
    date_days_ago = datetime.now() - timedelta(days=days_back)

    top_person = top_person.lower()
    posts = []
    top_person = top_person.replace("\"", "")  # clean
    r = webhose.search("persons:\"" + top_person + "\" domain_rank:<10000", since=int(time.mktime(date_days_ago.timetuple())))

    for post in r.posts:
        posts.append(post)

    while days_back > 0 or (len(r.posts) == 0):
        print "days_back = " + str(days_back)
        days_back -= 5

        r = webhose.search("persons:\"" + top_person + "\" domain_rank:<10000", since=int(time.mktime(date_days_ago.timetuple())))
        for post in r.posts:
            posts.append(post)

    return get_top_persons(posts, top_person)


# The main function that starts the collection of top mentioned persons
def main():

    # A dictionary of names and the top names mentioned around each one
    output = {}
    # Images of the people mentioned
    images = {}

    # Stating with Hillary Clinton
    person = "Hillary Clinton"

    # Get the top 5 people mentioned along side {person}
    persons = extract_top_persons(person)
    output[person] = persons


    # Make sure we don't query about this person again
    dup_check.add(person)

    # Queue the people we want to find the top people around them
    for person in persons:
        person_queue.put(person)
        dup_check.add(person)

    while not person_queue.empty():

        person = person_queue.get()
        persons = extract_top_persons(person)
        output[person] = persons
        # Make sure we don't query about this person again
        dup_check.add(person)

        # Break after 100 people queried
        if len(output) == 100:
            break

        for person in persons:
            if person in dup_check:
                continue
            dup_check.add(person)
            person_queue.put(person)

    # get the images for each person
    print "Getting the images for each person"
    for person in output:
        print "Getting the image for " + person
        images[person] = get_image(person)
        for connected_person in output[person]:
            print "Getting the image for " + connected_person
            images[connected_person] = get_image(connected_person)



    # Print the JSON to put into our JS file
    print json.dumps(output)
    print json.dumps(images)


if __name__ == "__main__":
    main()
