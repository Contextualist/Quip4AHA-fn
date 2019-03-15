from quip4aha import week, q4a, config, InvalidOperation

import itertools
import re
_bold_re = re.compile(r"(\*\*|__)(?=\S)(.+?[*_]*)(?<=\S)\1", re.S)
_br_re = re.compile(r'(?<!\n)\n(?!\n|$)')

def next_wedn():
    NextWednesday = week.RecentWeekDay('next Wednesday')
    return (
        NextWednesday.strftime("%m%d"),
        NextWednesday.strftime("%B %d").replace(" 0", " "),
    )

def tempgen(p_md):
     p = (_br_re.sub(r'<br/>', b) for b in p_md) # single \n -> br
     p = itertools.chain(*(b.split('\n') for b in p)) # split line
     p = (_bold_re.sub(r"<b>\2</b>", l) for l in p) # ** -> b
     # In the template, &#8203; (or &#x200b;) stands for a place-holder for a blank <p>.
     p = ["<p class='line'>"+(l or "&#8203;")+"</p>" for l in p][:-1]
     return '\n'.join(p)

def precondition():
    try:
        _ = q4a.latest_script_id
    except InvalidOperation as e:
        if e.code == 409:
            raise e # redundancy error
        #else: pass # script not found
    else:
        raise InvalidOperation("Redundancy Warning: The script has already been created.")

def post_newdoc(meta_id, template, title, date_lit):
    temp_id = q4a.copy_document(thread_id=meta_id)['thread']['id']
    anchor = re.search(r"<p id='([a-zA-Z0-9]+)'",
                       q4a.get_thread(id=temp_id)['html']).group(1)
    q4a.edit_document(thread_id=temp_id,
                      section_id=anchor, location=q4a.BEFORE_SECTION,
                      content=template)
    q4a.copy_document(thread_id=temp_id,
                      folder_ids=[q4a.AHABC_ID],
                      values={'date': date_lit, 'title': title})
    q4a.delete_thread(temp_id)


def NewDoc():
    precondition()
    template = tempgen(config['block'])
    title, date_lit = next_wedn()
    post_newdoc(config['metatemplate_id'], template, title, date_lit)
    return "Done!"

if __name__=="__main__":
    NewDoc()
